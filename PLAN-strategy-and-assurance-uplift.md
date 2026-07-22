# PLAN — Strategy & Value Self-Model, Assurance Explorability, Security Signals

Three coordinated work streams: (A) extend the ENG-ARCH-REPO self-model with a
principled strategy domain (capabilities, value streams, values, courses of action,
resources) bridging motivation ↔ business/application; (B) make assurance connections
first-class in the GUI (name-resolved links, ontology-driven edge authoring, neighbor
traversal, graph exploration, deep links); (C) dogfood dependency SBOMs and
vulnerability scans into the assurance signals store and surface entity-level security
metrics as virtual, non-editable attributes that ArchiMate viewpoints can style
(e.g. backend/frontend colored by max CVSS) and that entity detail pages show as
read-only derived attributes; plus (D) modelling-method defaults: a
hierarchy-generic guidance format for the pluralistic meta-ontology (each module's
declared levels; for archimate-4: domain / entity type / specialization) and
shipped default attribute schemata for business objects and the
application-component specializations Service, Module, and Endpoint; plus (E) a
documentation & deterministic-media workstream, (F) `arch-repair upgrade`
coverage for every changed persisted surface, and (G) a `motivation-coverage`
viewpoint (table of unrealized goals/outcomes/requirements with per-layer trace
diagnosis).

Companion files: `TASKS-strategy-and-assurance-uplift.md` (execution ledger),
`PROMPT-strategy-and-assurance-uplift.md` (executor prompt).

**Standing impact check** (required in every PLAN):
- *Self-model:* affected — covered by Part A (new content) and the sync WUs
  (B5, C5, the Part D requirements in §7.1, the Part G delta in §10.8, and the
  Part F upgrade-framework delta in §9.4).
- *Documentation:* affected — covered by Part E (README/docs/reference/media,
  synthetic fixtures for confidential content).
- *Upgrade/repair path:* affected in three places, each with its path: the
  signals-store schema change ships as an audited SQLCipher migration (WU-C0);
  attribute-schema defaults are additive and reach older repos via the existing
  ensure-missing pass, nothing required (D16); guidance cache format v2 keeps v1
  documents fully valid and importable (I-D2) with a mechanical
  header/provenance migration (§9). **The Repository Upgrade Framework itself is
  substantially extended** (Part F/§9: multi-target operational upgrade
  orchestration incl. guidance cache and both signal stores; the viewpoint
  declaration grammar of Part G is a further persisted-format row) — its
  self-model concepts are updated accordingly (§9.4).

---

## 1. Business context

The product recursively models itself in ENG-ARCH-REPO. Today the self-model has a
rich motivation layer (drivers, assessments, goals, outcomes, ~60
requirements, 7 stakeholders) and well-developed business/application layers — but a
**completely empty strategy domain**, although the ontology ships four strategy
viewpoints (`strategy`, `capability-map`, `value-stream`, `resource-map` with its
`investment_level` heat-map rule) and a `value` entity type that has never been
exercised. Part A closes that dogfooding gap and adds the missing "why does this
component exist → what ability → what value → for whom" trace spine.

The assurance store (SQLCipher, TLP:AMBER ceiling, unlocked in the dev workspace)
holds a 17-node/33-edge STPA/GRC graph, but the GUI renders assurance edges as
truncated raw IDs without links, offers no traversal or graph view, and authors edges
from a hardcoded type list — while the architecture side has all of these. Part B
closes that asymmetry at the correct layers.

The security-signals pipeline (BOM ingest, vulnerability import, anchor mappings) is
fully implemented but holds **zero data**, and nothing computes per-entity metrics.
Part C ingests the product's own backend (uv) and frontend (npm) SBOMs plus OSV
vulnerability data, adds a metrics read capability, and exposes signal-derived virtual
attributes to the viewpoint engine — ephemeral, unlock-gated, never persisted.

Actors: the owner (solo developer) and AI agents author everything; the future OSS
adopter is a modelled persona, not a present user. No multi-user authz beyond the
existing unlock/TLP and read-only gates.

**Scoping (Q12): the project is not yet public — the ENG-ARCH-REPO self-model
and its assurance store are EXAMPLE/dogfooding content.** Nothing in this
specific store is really confidential (its TLP labels exercise the product
mechanisms), and no third-party installations exist. Consequences: the
developer's own self-model and assurance store may be **migrated or recreated
freely** whenever a format changes (destructive re-refresh acceptable);
legacy-preservation and confidentiality invariants remain PRODUCT capabilities
proven on synthetic fixtures — never constraints derived from preserving this
store's content.

## 2. Locked decisions

- **D1 — Product strategy, not corporate strategy.** The strategy domain models the
  *solution-as-product*: its stable abilities, persona value streams, already-made
  strategic choices (evidenced by ADRs/decisions), and accumulated strategic assets.
  No revenue/market/go-to-market content, no fictitious org structures, no
  speculative community processes (guidance `never_create_when`: too volatile /
  situative).
- **D2 — The distinction strategy in §4.2 is normative** for Part A and for all
  future strategy-domain authoring: every new capability / value-stream (stage) /
  value / course-of-action / resource must pass its litmus tests, pairwise against
  neighbors and against existing requirements, processes, functions.
- **D3 — Reuse existing realizers.** Value-stream stages and capabilities are
  realized exclusively by *existing* processes/functions; Part A adds **no** new
  business-layer behavior. m:n realizations (one process realizing stages in two
  streams) are legal and expected (Open Group: stages frame processes; a process may
  realize multiple stages).
- **D4 — New artifact group `strategy-and-value`** for all Part A entities (values
  included, though they live in the motivation domain) so the nav facet cleanly
  separates the narrative.
- **D5 — Assurance edge endpoints are enriched server-side.** The node-read and
  edge-list use cases resolve endpoint names/types (exposure-policy filtered), and
  the GUI renders them as router links — the same contract the architecture
  `ConnectionsPanel` has. No client-side name lookup loops.
- **D6 — Edge authoring is ontology-driven over the reconciled, STPA-handbook-sound
  relationship model (owner-decided; WU-B0 implements).** Relationship kinds are
  separated first: (1) **assurance-edges** (both endpoints declared assurance node
  types → pair legality lives in `permitted_relationships`); (2)
  **architecture-references** (assurance node → architecture artifact via
  `arch_refs`, validated against a reference-type catalog: `binds-to`, `purl` —
  `binds-to` is never a node-pair matrix entry); (3) **external/reference-
  vocabulary links** (`cites`: obligation → `scheme:code` — its own typed
  representation, never a matrix row). The write path today validates endpoint
  existence but not pair legality (`src/application/assurance_mutations.py:193`);
  after WU-B0 the **loaded module catalog** (not raw YAML bytes — YAML→module
  loading is tested separately; transport adapters know nothing of file layout)
  is the single source for server-side create validation and GUI choices, and the
  matrix is **exhaustive**: an edge create violating it is rejected with a typed
  error. The reconciled semantics (validated against `spec/STPA_Handbook.pdf`):
  UCA→hazard is `leads-to` (a UCA "will lead to a hazard"; the handbook reserves
  violation for constraints — `violates` is dropped from the registry); system-
  level constraints derive from hazards and controller constraints from UCAs
  (`[hazard|unsafe-control-action, assurance-constraint, [derives]]`); type-b
  loss scenarios (a correct control action improperly executed, not executed,
  or improperly integrated) explain a hazard directly, without an intervening
  UCA (`[loss-scenario, hazard, [explains]]` — `leads-to` stays strictly causal
  between chain elements, `explains` is the scenario's epistemic relation; the
  pathway distinction is a `scenario_type` attribute on the scenario, never a
  hazard subtype); sub-hazards refine hazards
  (`[hazard, hazard, [refines]]`); controller responsibility is
  `[control-structure-node, assurance-constraint, [responsible-for]]`
  (rename of the unused `responsible-of`; handbook: responsibilities assigned to
  control-structure entities refine system-level constraints); risk ownership is
  `[control-structure-node, risk, [accountable-for]]` (rename + direction flip of
  `accountable-to`; ISO 31000 risk owner — the owner is an organizational
  controller in the control structure, optionally bound to the ArchiMate
  role/actor via the existing `binds-to`/`binding_status` machinery);
  `evidence` is a **declared assurance node type** (UCAs/CACs likewise stay
  reified nodes — the handbook's five-part UCA format needs own traceability)
  with `[assurance-constraint, evidence, [evidenced-by]]`, bound to implementing
  ArchiMate entities via the existing `binds-to`/`binding_status` convention,
  optional-but-flagged (unbound-pending = verifier finding); `satisfied-by` is
  dropped (unused, non-handbook). Verifier alignment: `stpa_complete` checks
  `uca_leads_to_hazard` and loss-scenario = explains→(UCA or hazard);
  E502 checks incoming `responsible-for`; `grc_complete` checks incoming
  `accountable-for`. The dev store repairs per Q12 (delete the 3 `violates`
  duplicates; convert the 4 `accountable-to` edges); deterministic repairs are
  registered as U0 operational data migrations.
  The catalog response **distinguishes edge types from reference types** so the
  GUI cannot submit one through the wrong mutation use case.
  The hardcoded 20-literal dropdown is deleted. Target selection
  extends the **existing** server-side assurance search endpoint
  (exposure-policy-filtered) — no second node-search implementation. Edge
  authoring in v1 is create + delete; there is **no edge-edit path** today and
  none is added.
- **D7 — One traversal endpoint with deterministic budgets, one generic canvas.**
  `GET /api/assurance/neighbors`: **deterministic size budgets define partial
  results; the time budget aborts the whole request** with a typed retryable
  error and no partial graph (wall-clock truncation is not deterministic — the
  two must never mix). Defaults, pinned in configuration with hard clamps:
  `max_hops` default 1, clamp 4; max 150 nodes; max 300 edges. Cycle-safe
  (visited set), exposure-omission per hop, unlock-gated, no-store. Response
  contract: deterministic ordering; `truncated=true` plus visible frontier node
  IDs when a size budget is hit — the client expands a frontier node with a new
  request; **no server-side continuation tokens in v1** (if ever added they must
  be opaque, integrity-protected, expiring, and bound to ceiling + availability
  revision + store snapshot); multiedge and self-loop behavior specified; the
  root is included and flagged; hop distance and direction on every node/edge;
  stable typed error envelopes. `GET /api/assurance/edge-catalog` serves loaded
  module configuration, not store content — it is **configured-gated but not
  unlock-gated**; content search and traversal remain unlock-gated.
  The canvas extraction defines the **generic input contract first**: normalized
  nodes/edges, loading + truncation state, selection/expansion callbacks, and
  presentation metadata — importing no architecture or assurance concepts —
  consumed by the architecture view (unchanged behavior) and the new assurance
  graph view.
- **D8 — Deep-linkable assurance node route** `/assurance/node/:id` reusing
  `AssuranceNodeDetail`; the browse split-view keeps its query-param behavior.
- **D9 — Security metrics are one pure application use case over an atomic
  refresh-run snapshot.** The current schema cannot represent an atomic "latest
  refresh": BOM ingests and vulnerability imports commit separately, and
  vulnerability records carry no refresh/anchor/component identity
  (`src/infrastructure/assurance/_schema.py`, `_security_connector.py`). Therefore
  a **security_refresh_run aggregate** is the foundation (WU-C0), with the
  §6.0(c) lifecycle as the single normative one
  (`staging → complete → active → superseded`, `staging → failed` terminal);
  `run_id`; started/completed/activated/superseded timestamps plus a stable
  tie-breaker; anchor; BOM digest, serial/version, generator/source versions;
  **component findings** and **vulnerability findings** owned by the run; **atomic
  activation** of a completed run; failed/stale runs retained for audit but
  excluded from metrics; an explicit retention policy. Metrics read exactly **one
  completed, active run snapshot per anchor** plus one exposure-policy snapshot.
  Metric vocabulary (unit-explicit): `distinct_open_vulnerabilities` (distinct
  canonical vulnerability identities, alias-resolved) and
  `open_component_findings` partitioned by directness class (direct | transitive |
  unknown — classified at ingest from the BOM dependency graph; dependencies of
  the BOM root component are direct; graph absent/malformed → unknown; per-class
  finding counts sum to the finding total — distinct-vulnerability counts do NOT
  partition by class, one vulnerability may hit several classes); per-severity
  band counts; `max_cvss_score` and `max_severity_band` per D12 (no fabricated
  scores); `component_count`; basis `run_id` + timestamp. **KEV is removed from
  v1** (no defined source/schema; requires CISA-KEV ingestion keyed by canonical
  identities — backlog). **VEX is a contextual assessment** keyed exactly per §6.0(d) —
  `(anchor_entity_id, canonical_component_id_incl_version,
  canonical_vulnerability_id)` — with disposition, justification, author,
  timestamp, and an audit event committed in the same transaction (D21); never a
  global flag on a vulnerability record; an audited VEX mutation (use case + REST + GUI flow) is
  in scope (C-S2 depends on it). MCP read tool + REST endpoint + the viewpoint
  provider (D10) all consume this single use case; no second computation site; no
  metric caching in v1. EPSS stays a **draft** self-model requirement (§6.1), no
  v1 implementation.
- **D10 — Virtual attributes via a dynamic, batched capability — not unlock-time
  injection.** Wiring happens at composition time while lock state changes at
  runtime, so the composition root always injects a **configured capability**
  (assurance-enabled deployments) or a **null capability** (disabled deployments);
  never conditional-on-current-lock. Layering: the domain model carries only the
  typed source discriminator; the pure graph-derived evaluator is untouched; the
  **application orchestration** partitions graph-derived vs external attributes,
  **batch-fetches** signal values for the retained population (one call, no
  per-entity/per-metric N+1), and constructs the evaluation environment; the
  infrastructure adapter calls the D9 metrics use case; ports live in
  `src/application/viewpoints/ports.py`. Every capability call evaluates current
  availability, exposure policy, and the active completed run, and one viewpoint
  execution pins one opaque `SignalSnapshotToken` (§6.0(f)) — returning either
  one coherent snapshot or an explicit `unavailable` result; it never mixes values fetched before and after a lock or
  run change. Unavailable → existing unresolvable-reference fallback (default
  styling plus an explicit "signals unavailable" legend note). The
  presentation-only deferral machinery applies unchanged.
- **D11 — Signal-derived styling is classification-bearing (computed, not
  hardcoded) and ephemeral, with an explicit render/export pipeline.**
  Classification is **computed from the contributing records** — the maximum
  contributing TLP — never hardcoded to AMBER (which would underclassify RED
  contributions). The public `signals_backend=sqlite` mode is **deprecated for
  metrics in v1** per §6.0(a)/Q10 — it has no population path; metrics run on
  the co-located backend. Every metrics
  payload and export carries: maximum contributing classification,
  `visibility_limited`, completeness/availability state, and basis run +
  timestamp. Rendering pipeline (the existing persisted-diagram download route is
  NOT reused): `POST` ephemeral render entirely in memory with
  `Cache-Control: no-store` and a classification banner derived from the payload;
  a separate `POST` export returns stamped bytes with `Content-Disposition`.
  Persistence refusal is decided by **viewpoint semantics** (the definition
  declares a signal source), never by whether values happened to resolve.
  Persisting such a render or its styling into any git-tracked artifact is
  refused; attribute values never enter entity files, exchange exports, or
  `types.generated.ts`. User-initiated download is permitted only through the
  stamped export path (banner = computed classification + generation timestamp).
- **D12 — Package identity, applicability, and severity semantics (safe by
  construction):**
  · **Package identity** uses a proper Package URL implementation with
  ecosystem-specific canonicalization (qualifiers/subpaths included) — never a
  partial string comparison of type/namespace/name.
  · **Applicability**: a finding exists when OSV's affected package/range entries
  match the component's version, or when the record was returned for exactly that
  queried component (the query→result mapping is stored as the finding). A
  version-unqualified vulnerability identifier is **`applicability_unknown`** —
  never "affects all versions"; unknown-applicability findings are counted
  separately and surfaced, not folded into open findings.
  · **Severity**: scores come only from real CVSS data — parse CVSS 2/3/4 vectors
  with a vetted scoring library, retaining vector, nomenclature, and source;
  expose `max_cvss_score` (from parsed vectors/scores only) and
  `max_severity_band` (qualitative). **Never fabricate a numeric score from a
  band**; records with neither vector/score nor band increment
  `unknown_severity_count`.
  · Vulnerabilities without any package identity are store-level stats only,
  never entity metrics.
  · **Canonical identity**: OSV aliases (CVE/GHSA/…) are resolved to one
  canonical identity per vulnerability so `distinct_open_vulnerabilities` never
  double-counts an alias pair.
- **D13 — Dogfooding is a repeatable refresh-run, not a one-off.** A script
  (`tools/refresh_security_signals.py`) generates the backend SBOM (CycloneDX from
  the uv environment) and frontend SBOM (`npm sbom --sbom-format cyclonedx` in
  `tools/gui`), acquires vulnerability data, and drives one **refresh run per
  anchor** (D9): stage → import → atomically activate; a crash before activation
  leaves the previous run active. OSV acquisition is two-phase per the API
  contract: `querybatch` returns compact id/modified results **aligned to request
  inputs and paginated** — each result is mapped back to its queried component —
  followed by per-id `GET /v1/vulns/{id}` fan-out with deduplication, retries,
  timeouts, and per-source partial-failure reporting; aliases are recorded for
  canonical-identity resolution (D12). The SBOM parser is extended to **preserve
  `bom-ref`, the metadata root component, and the `dependencies` graph** (the
  current `_sbom_parser.py` discards them), enabling directness classification.
  Anchors: backend → `APP@1777293133.OYEmP1` (Architecture Backend), frontend →
  `APP@1776149382.lmO0mp` (GUI Authoring Tool). Every user-requested execution creates a **new run**
  (BOM digest is content identity/provenance, never run identity); command retry
  idempotency uses a caller-provided `request_id` (§6.0.c). The script submits a
  typed refresh bundle to the single `RefreshSecuritySignals` application command
  (§6.0.b) — it imports no infrastructure connector.
- **D14 — No ontology changes to the architecture model** in Parts B/C (the
  assurance edge catalog is served from existing module config; viewpoint schema
  changes are viewpoint-definition schema, not entity ontology). Part A is pure
  model content (entities/connections/diagrams via MCP tools), zero code. Part D
  changes guidance/schema formats and shipped defaults, not entity/connection
  ontology.
- **D15 — Guidance format v2: hierarchy-generic levels (pluralistic
  meta-ontology).** The meta-ontology is pluralistic — each ontology module brings
  its own concept tree with its own number of hierarchy levels — so the guidance
  mechanics must NOT hardcode ArchiMate's shape. v2: each module **declares its
  guidance-addressable hierarchy levels** (registry-driven), and a guidance
  document may attach advisory `context` prose to any node of any declared level;
  serving composes additively along the concept's **ancestry path** in the owning
  module's tree, root-most first, ending at v1's per-type
  (`create_when`/`never_create_when`) and per-specialization entries; nothing
  overrides anything. Concretely for `archimate-4` the declared levels are
  **domain → entity type → specialization** (e.g. `domains.strategy` carries the
  strategy-vs-operating-model framing once for the whole domain); other modules
  (e.g. assurance) declare their own — possibly different —
  levels. There is deliberately **no meta-ontology-level `general` blob and no
  type-class level** — only levels a module actually declares exist. v1 documents
  (format 1) remain valid and importable unchanged; `--strict` validates each
  level key and node name against the owning module's declaration. The current
  extract is restructured to hoist the cross-type distinction framing (§4.2) to
  the domain level where it belongs, keeping type-level litmus lines local.
- **D16 — Shipped default attribute schemata on the EXISTING convention and
  resolver.** Per-specialization attribute schemata are **already implemented**:
  the filename convention is `attributes.<type>.<specialization>.schema.json` and
  `src/application/artifact_schema.py` already provides
  `compute_effective_attribute_schema` (merging base, inline specialization
  attributes, and attachment schema). This part **adds schema payloads and
  extends/verifies the existing resolver — it does not introduce a new convention
  or a second resolver**; WU-D2 verifies all current consumers (validator, GUI
  typed editor, registry snapshot) delegate to the one resolver. Defaults land in
  `DEFAULT_SCHEMATA` (`_repo_default_schemata.py`), ensured into new AND existing
  engagement/enterprise repos by the template's existing ensure-missing pass
  (existing files are never overwritten — load-bearing, already implemented in
  `engagement_repo_template.py`). Additionally ships
  `attributes.resource.schema.json` declaring `investment_level` (integer, 1–5,
  band meanings documented, not required) — without it the shipped `resource-map`
  heat-map deliberately falls back (see the existing heat-map tests), which would
  make Part A's heat-map acceptance unattainable. `format: uri` on Source
  Repository is **informative** (GUI hint): the JSON Schema validator runs without
  a format checker, so it is not server-enforced — stated in the schema
  description. Two unified,
  single-sourced enums: **Sensitivity** = `Public | Internal | Confidential |
  Strictly Confidential` (planner-friendly; TLP mapping documented in the schema
  description: Public≈WHITE, Internal≈GREEN, Confidential≈AMBER, Strictly
  Confidential≈RED) and **Lifecycle State** = `Planned | In Development | Active |
  Deprecated | Retired` (shared by Service, Module, Endpoint). Shipped sets:
  · business-object — Meaning (string), Provenance (string), Contained Information
  (string list), Internal Consistency Criteria (string list), External Consistency
  Criteria (string list), Sensitivity (enum), Lifecycle States (string list — the
  states an information object instance passes through; deliberately distinct in
  name and meaning from the component-level Lifecycle State enum, disambiguated in
  both descriptions);
  · application-component--service — Programming Languages & Versions, Frameworks
  & Versions, Runtime Environments, Communication Protocols & Versions (string
  lists), Owner (string), Source Repository (string, format uri), Lifecycle State
  (enum);
  · application-component--module — Problem Domain (string), Lifecycle State
  (enum) — no Owner: a module sits hierarchically below a service, whose Owner it
  inherits;
  · application-component--endpoint — Communication Protocol & Version (string),
  Authentication Method (string), Lifecycle State (enum).
  **Nothing is required** (`required: []`, `additionalProperties: true`), so
  existing entities keep validating and the startup schema policy stays green.
  Dogfooding is part of the deliverable, not a spot-check: `Architecture Backend`
  and `GUI Authoring Tool` currently have **no specialization and no properties**
  — WU-D2 sets `Architecture Backend` to specialization `service` and fills its
  attribute set via MCP (guidance-checked), giving documentation a real example.
- **D17 — Entity details show derived security attributes read-only.** When the
  assurance store is unlocked and D9 metrics exist for an architecture entity, its
  detail page shows the signal-derived attributes in a dedicated read-only panel:
  visually offset background, classification icon per the payload's **computed**
  classification (D11), basis run + timestamp, completeness/availability state.
  Sourced from the D9 use case over the assurance REST read surface (gated exactly
  like the existing assurance lens: hidden when locked/absent/empty).
  **Structurally separate from the editable properties model** — the values never
  enter the entity edit payload, so no edit round-trip can persist them (I-C1).
- **D18 — Documentation & media are in scope, with synthetic confidential data
  only.** Part E updates user-facing documentation to the current product (the
  docs already describe content-first navigation while `docs/media/*` screenshots
  still show the old tier-first header and stale counts) and regenerates a
  deterministic screenshot suite. Two hard rules: (i) screenshots showing
  security metrics or assurance content use an **explicitly synthetic TLP:WHITE
  documentation fixture** with a visible "Synthetic documentation data" marker —
  never the developer's live assurance store (extending today's media suite,
  which captures a live unlocked stack into tracked `docs/media/`, to the metrics
  panel would violate I-C1); fixtures come via route interception or a dedicated
  seeded test connector, with **no documentation bypass in production code**;
  (ii) screenshots select **stable entity IDs**, never "first result". The README
  claim that every screenshot is the system describing itself is amended to
  distinguish self-model content from synthetic confidential-data examples.
- **D20 — Motivation-coverage viewpoint (Part G; contract = §10).** A new
  shipped viewpoint `motivation-coverage` reports **branch-complete full
  realization** per §10.2: verdicts `pass | gap | not_applicable` with stable
  status codes; branch enumeration over **direct stored motivation edges** and
  leaf coverage via derived realization chains (§10.2a); parameters `scope`
  (enum-set, §10.3) + `gaps_only` + `group`, executed through the §10.3b
  pipeline (trace evaluation precedes computed filtering, global sorting, and
  limiting); one **row projection DTO** containing the discriminated
  `PatternResult` union (authoritative verdict vs diagnostic observation) for
  GUI/REST/CSV; structural + request-wide budgets (§10.5); an **executed table, never a saved diagram** (§10.6). The
  declaration grammar **is a persisted-format change** (§10.7 → §9.1 row). The
  existing `requirements-coverage-gaps` viewpoint stays, cross-referenced. No
  entity-ontology change (D14 unaffected).
- **D21 — Signal-mutation audit durability.** No accepted signal mutation may
  exist without its durable audit record committed in the **same unit of
  work**; therefore mutations are allowed only under the §6.0(a) capability
  predicate (store `sqlcipher` + signals `sqlcipher-colocated` + archive
  `standard|worm` + unlocked — one SQLCipher transaction owns signal SQL and
  audit-row SQL; adapters that commit independently are refactored, never
  wrapped). Every other store × signals × archive × lock combination denies
  mutations with a typed capability reason; public `signals_backend=sqlite`
  metrics are deprecated in v1 (Q10). Full contract: §6.0(a).
- **D19 — Every changed persisted surface is covered by `arch-repair upgrade`
  (architecture = §9.2).** Every persisted-format change ends in exactly one
  of: (1) backward-compatible with a detector proving it; (2) auto-migratable
  through a registered upgrade step; (3) blocking finding with complete manual
  instructions before any commit writes. Targets are deployment-scoped (§9.2:
  workspace selects repositories; operational targets bind to an explicit
  settings/deployment identity; Docker cannot exclude configured active
  targets). Guidance-cache migration is a **header/sidecar-only
  transformation** (leaf guidance bytes preserved via text patch — §9.2);
  legacy signal data is quarantined per exact DDL and never given fabricated
  semantics. Persisted-format evolution belongs in `arch-repair upgrade`,
  never `arch-repair git-repair`.

## 3. Current state (verified)

Model (via `artifact_query_stats` / listings, 2026-07-19 — totals are a volatile
snapshot; never treat absolute counts as acceptance targets, use live stats and
deltas at execution):
- ~410 entities, ~800 connections; `entities_by_domain` has **no `strategy` key** —
  zero CAP/COA/RES/VS entities; zero VAL entities.
- **No `attributes.resource.schema.json` exists** in the self-model repo, so the
  shipped `resource-map` heat-map falls back to default styling (the styling
  engine deliberately warns without a declared `investment_level`) — WU-A0 must
  land the schema before WU-A4.
- `Architecture Backend` and `GUI Authoring Tool` carry **no specialization and no
  properties** today.
- Impact analysis excludes Association from derivation composition (no direction
  to propagate; documented in `docs/03-modeling/impact-analysis.md`), and
  `element-dependents` is an incoming, certain-only traversal capped at 4 hops —
  persona/value hops (associations) are NOT reachable by it; acceptance uses
  explicit witness chains instead (§4.9).
- Existing realizer inventory for Part A (all present): processes `Architecture
  Modelling & Planning`, `Architecture Implementation`, `Architecture Conformance
  Review`, `Reverse Architecture`, `Promote Artifacts`, `Initialize Repository`,
  `Conduct Hazard Analysis`, `Manage Risk & Compliance`, `Build Assurance Case`,
  `Investigate Incident`; functions incl. `Ingest & Reconcile Supply-Chain Signals`,
  promotion functions, authoring/verification functions; stakeholders Architect,
  Developer, DevOps Engineer, Product Owner, Upper Technical Management, Risk &
  Compliance Officer, Safety/Security Analyst.

Assurance GUI (file:line verified):
- `AssuranceNodeDetail.vue:218-248` renders edges as plain `{{ edge.target_id }}` /
  `{{ edge.source_id }}` text, CSS-truncated (`max-width:130px`, lines 376-381); no
  names, no links. Architecture `ConnectionsPanel.vue:224-229` renders name-resolved
  `RouterLink`s. `AssuranceDiagramPanel.vue:306-336` already links endpoints to
  `/assurance/browse?node_id=…` — in-tree precedent, inconsistent with the detail
  view.
- Backend `_assurance_read.py:133-142` returns edges as raw dicts without endpoint
  name resolution. **No `/api/assurance/neighbors` or any traversal endpoint
  exists**; architecture has `GET /api/neighbors` (`connection_read_routes.py:36`).
- `AssuranceEdgePicker.vue:20-25` hardcodes 20 connection-type literals; target
  search fetches the whole node list and filters client-side (lines 40-68); no
  incoming-direction creation; no edge edit; `DELETE /edges/{edge_id}` exists
  (`_assurance_write.py:194`) but is unreachable from the detail view.
- `src/ontologies/assurance/connections.yaml` declares 20 connection types **and**
  a `permitted_relationships` pair matrix (lines 131-149) — the matrix is
  **incomplete** (types incl. accountable-to, responsible-of, evidenced-by, cites,
  binds-to are declared or in active use but absent from it), it is unused by the
  GUI, and the write path (`src/application/assurance_mutations.py:193`) validates
  endpoint existence but **not** pair legality.
- The exposure policy **intentionally omits an edge unless both endpoints are
  visible** (`src/application/assurance_exposure.py:114`; REST behavior in
  `_assurance_read.py:122`), and absent vs above-ceiling direct reads are
  deliberately indistinguishable — any Part B change must preserve exactly this
  contract (no placeholders).
- Routes: no per-node route; detail is `/assurance/browse?node_id=…` only.

Security signals:
- Store unlocked; `assurance_security_stats` = 0 BOMs / 0 components / 0 vulns /
  0 anchors. Connector supports CycloneDX+SPDX ingest and vuln records with
  `cvss_score`/`severity`/`vex_status` (`_security_connector.py`), **but**:
  BOM and vulnerability imports commit at separate points (no atomic refresh);
  vulnerability records carry **no** run/ingest/anchor/component identity and
  `vex_status` is a **global** flag on the record (`_schema.py:158`); severity/
  CVSS are stored verbatim with no vector parsing; the SBOM parser
  (`_sbom_parser.py`) **discards `bom-ref`, the metadata root component, and the
  dependency graph**; nothing computes derived per-entity metrics. A public
  `signals_backend=sqlite` mode exists and its adapter is currently writable
  (creates directories/tables) — this plan **deprecates its metrics capability
  in v1** (Q10/§6.0(a)); upgrade emits a migration finding.
- Viewpoint engine: `DerivedAttribute` (`src/domain/viewpoint_bindings.py:36`) is
  graph-traversal-only (direction/traversal/criteria/reduce). Presentation-only
  derived attributes are lazily deferred
  (`src/domain/viewpoint_derived_attribute_deferral.py`). Scale/heat-map styling over
  numeric attributes exists (`viewpoint_style_evaluation.py`; `resource-map`
  `investment_level` precedent). Unresolvable references degrade to default styling.
- Attribute schemata: the per-specialization convention
  `attributes.<type>.<specialization>.schema.json` is **already implemented and
  documented** in `src/application/artifact_schema.py`, which also provides
  `compute_effective_attribute_schema` (base + inline specialization + attachment
  merge); the ensure-missing template pass preserving user files exists in
  `engagement_repo_template.py`.
- Viewpoint table machinery (verified for Part G — full baseline in §10.1):
  table presentation with entity-field-only columns, `group_by`, badge rules,
  and CSV exist; parameters are scalar-only (`string|integer|number|date|
  boolean|slug|entity-id` — no collection type), the parameter prompt opens
  only for required-without-default, binding resolves values as operands only,
  `max_query_parameters` = 4, table limiting runs in the existing execution
  path with no post-trace filter/sort phase. Part G's mechanism gaps are
  therefore: computed columns, the enum-set parameter type, the post-projection
  pipeline phase, and the always-visible parameter toolbar (§10.1/§10.3).
- Documentation: `docs/03-modeling/views-and-exploration.md` already describes
  content-first navigation/tier facets, but `docs/media/*` screenshots predate the
  navigation change (old ENGAGEMENT/GLOBAL header, stale hero counts); the media
  suite (`tools/gui/tests/media/media.spec.ts`) captures a **live unlocked
  assurance stack** into tracked `docs/media/` and picks the detail-view entity
  dynamically ("first result").
- SBOM tooling on this machine: no osv-scanner/syft/trivy; npm ≥9.5 `npm sbom`
  available; `uvx cyclonedx-py` viable for the Python environment; OSV.dev batch API
  requires network only.
- Exposure-policy + no-plaintext precedents exist: `assurance_search` no-store +
  `test_assurance_search_safety.py` (no-new-file, concurrency).

## 4. Part A — Strategy & value self-model

### 4.1 Research base

Project guidance (authoritative, via `artifact_authoring_guidance`) for capability,
course-of-action, resource, value-stream, value, process, function, service, goal,
outcome, requirement — the `create_when` / `never_create_when` texts drive the tests
below. External corroboration (Open Group / BIZBOK secondary literature):
value streams & capabilities express the **business model, organization-independent**;
processes & functions express the **operating model, organization-dependent**; value
stream + process = "enterprise in motion", capability + function = "enterprise at
rest"; stages carry participating stakeholders, entrance/exit criteria, and a **value
item**; value streams are named verb-noun in active tense; capabilities enable
(serve) value-stream stages; processes realize stages m:n.
Sources: [Bizzdesign — BIZBOK↔ArchiMate mapping](https://bizzdesign.com/blog/business-architecture-redefined-mapping-bizbokr-archimater),
[Bizzdesign — Value Stream Mapping](https://bizzdesign.com/blog/archimate-and-value-mapping/),
[Visual Paradigm — Value Stream in ArchiMate](https://www.visual-paradigm.com/guide/archimate/how-to-use-value-stream-in-archimate/),
[Hosiaisluoma — Value Stream Modelling](https://www.hosiaisluoma.fi/blog/value-stream-modelling/),
[Biz Arch Mastery — the BA value stream](https://bizarchmastery.com/straighttalk/value-mindset-demystifying-business-architecture-value-stream).

The §4.2 litmus distinctions are also **woven into the deployment guidance**
(2026-07-19): `~/.arch-guidance-extract/archimate-4.guidance.yaml` (capability,
value-stream, value, outcome, requirement, process, function, course-of-action
entries) and imported via `arch-import-guidance --strict` (44 matched, 0 unmatched)
into `~/.config/arch-repo/guidance-cache/` — live on MCP/GUI surfaces after the next
backend restart, so executors of Part A receive the distinctions from
`artifact_authoring_guidance` itself.

### 4.2 Entity-type distinction strategy (normative litmus tests)

Classify a candidate by answering in order; the first decisive answer wins.

| # | Test (ask of the candidate) | If yes → |
|---|---|---|
| T1 | Is it a statement of *worth to a beneficiary* (interest-relative, n:m to elements, no achievement date)? | `value` |
| T2 | Is it a *measurable/observable achieved state* contributing to a goal? | `outcome` |
| T3 | Is it a *testable obligation* the architecture must satisfy ("must…")? | `requirement` |
| T4 | Is it a *normative rule guiding all design* rather than a satisfiable need? | `principle` |
| T5 | Is it a *chosen approach* organizing resources/capabilities toward outcomes (a decision one could have made differently)? | `course-of-action` |
| T6 | Is it *in motion* (has entrance/exit criteria and produces an incremental value item for a persona), stated organization/tool-independently? | `value-stream` (stage) |
| T7 | Is it *at rest* and would it survive a complete re-implementation with different components and processes? | `capability` |
| T8 | Is it *at rest* but performed by assignable roles/components of THIS product (operating model)? | `function` |
| T9 | Is it *in motion* as a causally/temporally ordered way THIS product does something? | `process` |
| T10 | Is it behavior *as seen by an external consumer at an interface*? | `service` |
| T11 | Is it a *strategic asset* (owned/controlled, feeds capabilities)? | `resource` |

**T-N (naming rule, applies to every entity):** a name must be intelligible to a
generally and domain-knowledgeable practitioner **without further context** — spell
out its X/Y references ("Feed Implementation Learnings Back into the Architecture
Model", never "Feed Learnings Back"), and never name a value-stream stage after the
activity that realizes it (near-duplicating a process/function name) — name it after
the value produced. This rule is also woven into the imported authoring guidance
(value-stream entry).

Pairwise corollaries used in §4.3: **capability vs stage** = at-rest vs in-motion;
**capability vs function** = survives re-implementation vs assigned to concrete
components; **stage vs process** = value item + persona framing vs concrete ordered
behavior (m:n realization expected, near-duplicate *names* forbidden — rename the
stage to its value, not the activity); **value vs outcome** = standing worth vs
achieved state; **capability vs requirement** = descriptive ability vs normative
obligation (they meet via `capability —realization→ requirement` only where the
capability as a whole is the satisfier); **COA vs principle** = revocable chosen
approach vs standing norm.

### 4.3 Per-entity judgment (one-by-one)

Verdicts: **KEEP** (as proposed), **REFINED** (kept, definition/name/links tightened),
**DROPPED** (fails a test or does not earn its keep).

**Capabilities**

| Candidate | Verdict | Judgment |
|---|---|---|
| Architecture Knowledge Management | KEEP | T7: survives re-implementation (the ability to capture/organize/verify architecture knowledge is what the product *is*, however built). Distinct from SRV `Architecture Management System` (T10 consumer view) and from authoring functions (T8). Realized by `Author Model Artifacts`, `Index Repository`, `Verify Artifact Integrity & Coherence` (functions) and `Architecture Modelling & Planning` (process). |
| Agent-Native Architecture Collaboration | REFINED | T7 pass, but must be defined as the *ability* (humans and AI agents co-author the same knowledge with equal-fidelity surfaces), not restate PRI `…Human and Agent Interfaces` (T4 norm) or REQ `Tool Interfaces: MCP, CLI, REST` (T3 obligation). Realized by `Retrieve Architectural Context`, `Synthesize & Deliver Implementation Guidance`, `Author Model Artifacts`. The capability→requirement realization to `Tool Interfaces: MCP, CLI, REST` is the canonical example of the T3/T7 bridge. |
| Tiered Knowledge Governance | REFINED | T7 pass ("Promotion" removed from the name — promotion is motion; the standing ability is governed tiering). Realized by `Promote Artifacts` (process) + `Execute Promotion`, `Detect Promotion Conflicts`, `Validate Promotion Selection` (functions). |
| Integrated Safety, Security & Compliance Assurance | KEEP | T7 pass; realized by `Conduct Hazard Analysis`, `Manage Risk & Compliance`, `Build Assurance Case`, `Investigate Incident` (processes) and `Ingest & Reconcile Supply-Chain Signals` (function). Anchors Part C's strategy trace. |
| Architecture Analysis & Visualization | REFINED | Renamed from "Insight & Visualization". T7 pass; distinct from #1 pairwise: #1 = keep knowledge correct, #5 = derive answers/presentations from it. Realized by `Graph Traversal`, `Check Model Coverage`, `Author Diagrams` (functions). |
| Extensible Ontology & Method Configuration | DROPPED | Fails "earns its keep": the norm is PRI `Extensibility and Configurability`, the obligations are the configurable-* REQ family, and the traceability question ("what realizes extensibility?") is already answered by requirements-realization over those REQs. Revisit only when third-party ontology modules become a live adoption story (then it is a genuine business-model ability). |

**Value streams & stages** (verb-noun active names; each stage gets summary =
value item + entrance/exit criteria; stakeholder associations at stream level)

| Candidate | Verdict | Judgment |
|---|---|---|
| VS-1 Deliver an Architecture-Aligned Change (Developer, AI Agent, Architect) | REFINED | T6 pass end-to-end; all stage names re-checked against T-N. Stages: *Scope & Plan an Architecture Change* (value item: agreed intent) → *Model & Validate the Architectural Design* (validated model delta) → *Implement with Architectural Guidance* (conformant implementation) → *Confirm Architecture Alignment* (verified alignment — renamed from "Review Conformance", which near-duplicated the process `Architecture Conformance Review`) → *Feed Implementation Learnings Back into the Architecture Model* (shared model reflects reality — "Feed Learnings Back" failed T-N: no self-contained X/Y). Realizations: `Architecture Modelling & Planning` → stages 1-2; `Architecture Implementation` → 3; `Architecture Conformance Review` → 4; `Reverse Architecture` + `Refine Architecture Content after Implementation` → 5. |
| VS-2 Assure a System Release (Safety/Security Analyst, Risk & Compliance Officer) | REFINED | T6 pass. Stage 3 renamed from "Ingest Supply-Chain Signals" to **Contextualize Supply-Chain Risk** — the original was a near-duplicate of FNC `Ingest & Reconcile Supply-Chain Signals` (stage names the value: external risk knowledge bound to the architecture; the function names the activity). Stages: *Establish the Assurance Analysis Context* → *Analyze Hazards & Threats* → *Contextualize Supply-Chain Risk* → *Treat Risks & Track Compliance Obligations* → *Build & Seal the Assurance Case* (T-N applied). Realizations: `Conduct Hazard Analysis`, `Ingest & Reconcile Supply-Chain Signals` (+ Part C's new process), `Manage Risk & Compliance`, `Build Assurance Case`. |
| VS-3 Grow Reusable Enterprise Knowledge (Architect, Upper Technical Management) | KEEP | T6 pass; value item chain ends in cross-engagement reuse — the two-tier product story. Stages: *Author Architecture Content in the Engagement* → *Validate & Review Promotion Candidates* → *Promote to the Enterprise Tier* → *Reuse Enterprise Knowledge Across Engagements* (T-N applied). `Promote Artifacts` legally realizes both VS-1 "Feed Implementation Learnings Back into the Architecture Model" and VS-3 "Promote to the Enterprise Tier" (m:n per D3 — deliberate, documented in both connection descriptions). |
| VS-0 Adopt the Platform (Platform Adopter — new stakeholder) | KEEP (flagged) | T6 pass; this is the stream the publication-readiness/docs efforts serve, so it earns its keep *now* even pre-announcement. Stages: *Discover & Evaluate the Platform* → *Install & Configure the Platform* → *Import Authoring Guidance* → *Model the First Engagement* (T-N applied). Realized by `Initialize Repository` (process), `Load Guidance Content`, `Check Repository Workspace Status` (functions); *Discover & Evaluate the Platform* has documentation, not model behavior, as realizer — acceptable gap, noted in the stage description. Most volatile of the four: revisit wording at announcement time (D1 keeps GTM content out regardless). |

**Values** (motivation domain, group `strategy-and-value`)

| Candidate | Verdict | Judgment |
|---|---|---|
| Architectural Clarity at Agentic Velocity | KEEP | T1 pass (worth to Developer/AI Agent/Architect; no achievement date). Pairwise vs OUT `Reduced Planning & Governance Overhead`: the outcome is a measurable achieved state (T2), the value is the standing worth that state serves. |
| Provable Assurance Without Specialist Overhead | KEEP | T1 pass (Analyst/Officer; mirrors DRV `Safety, Security & GRC Capability Gap for Small Teams` from the beneficiary side). |
| Compounding, Reusable Architecture Knowledge | KEEP | T1 pass (UTM/Architect); VS-3's value item at stream level. |
| Low-Friction Adoption | REFINED | T1 pass but sharpened to stay interest-relative, not measurable-target (that would be T2): worth = "an adopter can trust the platform enough to commit before investing specialist effort". Associated with VS-0 and STK Platform Adopter only. |

**Courses of action**

| Candidate | Verdict | Judgment |
|---|---|---|
| Develop Privately, Release as Open Source | KEEP | T5 pass (a revocable chosen approach; the staged-announcement posture). Links: influence → OUT `Proven Patterns Promoted and Adopted Across Engagements` is wrong (that outcome is about promotion) — **no existing outcome fits adoption**; keep goal-level association only (`Lower the Barrier to Rigorous Assurance Work` assoc is also wrong). Association to DRV `AI-Assisted Development as Dominant Production Mode` + STK Platform Adopter; realization target deliberately left open until an adoption outcome legitimately exists (iterative-modeling principle: valid intermediate state). |
| Dogfood via the Recursive Self-Model | KEEP | T5 pass. influence → OUT `Increased Architectural Coherence`, realization → OUT `Assurance Analysis Surfaces Modeling Gaps` (dogfooding assurance is precisely how that outcome is achieved). Capability `Integrated …Assurance` and `Architecture Knowledge Management` realize it. |
| Guidance-First, License-Separated Method Content | KEEP | T5 pass (one could have baked guidance in; the separation is a strategic choice enabling OSS). realization → REQ `Deployment-Level Guidance Import` (COA→requirement realization is legal and here genuinely the satisfier-of-need relation); association → PRI/REQ extensibility family. |

**Resources**

| Candidate | Verdict | Judgment |
|---|---|---|
| Enterprise Architecture Knowledge Base | KEEP | T11 pass; realized by BOB `Enterprise Repository`; assigned to `Tiered Knowledge Governance` + `Architecture Knowledge Management`. `investment_level: 4`. |
| Recursive Self-Model (ENG-ARCH-REPO) | KEEP | T11 pass; realized by BOB `Engagement Repository`; assigned to `Architecture Knowledge Management`; assignment → COA `Dogfood via the Recursive Self-Model`. `investment_level: 5`. |
| Modelling & Method Guidance Corpus | KEEP | T11 pass; realized by DOB `Architecture Modelling Guidance` + DOB `Assurance Method Guidance`; assigned to `Agent-Native Architecture Collaboration` + `Integrated …Assurance`. `investment_level: 3`. |
| Assurance Knowledge Base | KEEP | T11 pass; realized by DOB `Assurance Knowledge Base`; assigned to `Integrated …Assurance`. `investment_level: 4`. |

**New stakeholder:** `Platform Adopter` (motivation) — prospective solo developer /
small team evaluating the OSS release; required by VS-0/T6 (a stream needs its
beneficiary). Engagement-local (promotion to enterprise is a later decision — related
open question exists in the backlog about engagement-local viewpoint stakeholder
references).

### 4.4 Set-level and holistic judgment

- **Type-set level.** 5 capabilities (each pairwise distinct under T7/T8; none is a
  renamed function), 4 streams / 18 stages (each stage has a distinct value item;
  every stage name passed the T-N self-containedness rule, with three renames fixing
  process/function near-duplicates or missing referents), 4 values
  (each tied to ≥1 stream + ≥1 stakeholder; none measurable-dated), 3 COAs (each a
  revocable decision with ADR-grade evidence), 4 resources (each feeds ≥1
  capability). No candidate survives that duplicates an existing requirement,
  process, function, principle, or outcome under §4.2.
- **Holistic.** Total: 39 entities (1 STK, 4 VAL, 5 CAP, 3 COA, 4 RES, 4 VS, 18 VS
  stages), ~80 connections, exactly 8 diagrams. This is the *minimal sufficient* set that
  (i) makes all four shipped strategy viewpoints render meaningfully, (ii) closes the
  motivation↔business trace gap via the §4.9 witness chains (associations make a
  single derived component→persona query impossible by design), and (iii) gives assurance losses a value frame (Part C ties into
  VS-2 stage 3). Nothing in the set requires maintenance on feature-level change —
  the volatility ceiling of the strategy layer is respected. Largest residual risk:
  stage inflation in future sessions — D2 makes §4.2 the gate.

### 4.5 Connection inventory (types verified legal against guidance)

- Stages: `VS —composition→ stage`, `stage —flow→ next stage` (within each stream).
- `capability —serving→ stage` (map per §4.3; each stage served by 1-2 capabilities).
- `process/function —realization→ stage` and `—realization→ capability` (per §4.3).
- `resource —assignment→ capability` (+ `resource —assignment→ COA` for Self-Model→Dogfood).
- `capability —realization→ course-of-action` (guidance: capabilities realize COAs).
- `COA —realization/influence→ outcome`; `COA —realization→ requirement` (Guidance-First only).
- `capability —realization→ requirement` (Agent-Native → `Tool Interfaces: MCP, CLI,
  REST`; Integrated Assurance → `Assurance to Architecture Linkage`; Tiered
  Governance → `Two-Tiered Repository`, `Promotion Mechanism to Enterprise Repository`).
- `VS ↔ value` association; `value ↔ stakeholder` association; `stakeholder ↔ VS`
  association (participation), `value —influence→ outcome` where the worth motivates
  a modeled outcome (e.g. Provable Assurance → `Assurance Friction & Guidance
  Overhead Reduced`).

### 4.6 Diagrams (full specs — audience, question, population, checks)

Common rules: PUML rules from the modelling skill apply; every diagram carries a
legend where banding/heat is used; the post-render assertion column is objective
and checked (and recorded) at WU-A4. **Exactly 8 diagrams.** Population
mechanism: the four shipped strategy viewpoints are **unparameterized broad
queries**, so every diagram below is created with an **explicit `entity_ids`
population** (recorded from the IDs produced in WU-A1/A2 before WU-A4) with the
named viewpoint attached for scope/presentation validation — never by executing
the unrestricted query. Each diagram gets a pre-render population assertion and a
post-render node/edge count assertion.

| Diagram | Audience / question | Population & viewpoint params | Excluded | Layout / density budget | Post-render assertions |
|---|---|---|---|---|---|
| Strategy overview (`strategy` viewpoint) | Owner, future contributors / "what is this product's strategy in one picture?" | All 5 CAP, 3 COA, 4 RES, 4 VS parents (no stages), plus exactly the two COA-linked outcomes: `OUT@1712870400.LrpdG0` Increased Architectural Coherence and `OUT@1780655839.Vhhne7` Assurance Analysis Surfaces Modeling Gaps → 18 nodes | Stage VSs, values, stakeholders, requirements | LTR; ≤ 20 nodes / ≤ 32 edges | Node count == 18; every CAP has ≥1 realization in; every COA reaches ≥1 outcome or requirement; no orphan node |
| VS-1..VS-0 value-stream diagrams (×4, `value-stream` viewpoint) | Persona owners / "how does value flow through this stream and what serves each stage?" | One stream: parent + its stages, serving CAPs, its value(s), its stakeholder(s)/role | Other streams, COAs, resources | LTR flow spine; ≤ 14 nodes each | Stage chain is a single flow path; every stage has ≥1 serving CAP (VS-0 stage 1 exempt, documented); value and persona attached at stream level |
| Capability map (`capability-map` viewpoint) | Owner / "which abilities exist and what feeds them?" | 5 CAP, 4 RES, linked outcomes | VSs, COAs | TTB; ≤ 12 nodes | Every RES assigned to ≥1 CAP |
| Resource map (`resource-map` viewpoint) | Owner / "where is investment concentrated?" | 4 RES (+ CAP context) | Everything else | TTB; ≤ 10 nodes | Heat-map banding visibly applied from `investment_level` (no fallback warning — requires WU-A0 schema) |
| Capabilities × stages matrix | Owner, reviewers / "which capability serves which stage?" (dense m:n) | 5 CAP rows × 18 stage columns, serving connections | — | Matrix | Every stage column non-empty except VS-0 stage 1; matches §4.7 exactly |

Maintenance: the strategy group's owner is the repository owner; the review
trigger is any business-model-level change (public announcement, licensing/tier
change) — not feature work (D1). Recorded in the group description.

### 4.7 Stage map (normative execution reference)

Capability abbreviations: **AKM** Architecture Knowledge Management · **ANC**
Agent-Native Architecture Collaboration · **TKG** Tiered Knowledge Governance ·
**IA** Integrated Safety, Security & Compliance Assurance · **AAV** Architecture
Analysis & Visualization. Each row: the stage's value item, the capabilities
serving it, and the existing realizers (IDs in §4.8).

**Entrance/exit criteria (normative, complete):** exit(stage n) = "value item n
delivered" = entrance(stage n+1) — adjacent criteria are equal by construction and
each stage summary states both. The stream boundaries are: VS-1 entrance(1) = a
change need or idea is articulated; exit(5) = the shared model reflects the
implemented system. VS-2 entrance(1) = an assurance obligation or concern exists
for a release; exit(5) = a sealed, tamper-evident assurance case exists for it.
VS-3 entrance(1) = engagement work produces potentially reusable content;
exit(4) = another engagement consumes the promoted knowledge. VS-0 entrance(1) =
a prospective adopter learns the platform exists; exit(4) = their first engagement
model answers a real question for them.

**VS-1 Deliver an Architecture-Aligned Change**
| # | Stage | Value item | Serves | Realized by |
|---|---|---|---|---|
| 1 | Scope & Plan an Architecture Change | agreed change intent and scope | AKM, ANC | Architecture Modelling & Planning |
| 2 | Model & Validate the Architectural Design | validated model delta | AKM, ANC | Architecture Modelling & Planning |
| 3 | Implement with Architectural Guidance | conformant implementation | ANC | Architecture Implementation |
| 4 | Confirm Architecture Alignment | verified implementation↔architecture alignment | AAV | Architecture Conformance Review |
| 5 | Feed Implementation Learnings Back into the Architecture Model | shared model reflects implemented reality | AKM, TKG | Reverse Architecture; Refine Architecture Content after Implementation; Promote Artifacts (m:n with VS-3.3) |

**VS-2 Assure a System Release**
| # | Stage | Value item | Serves | Realized by |
|---|---|---|---|---|
| 1 | Establish the Assurance Analysis Context | analysis scoped and anchored to architecture elements | IA, AKM | Author Assurance Artifacts |
| 2 | Analyze Hazards & Threats | identified losses, hazards, UCAs, constraints | IA | Conduct Hazard Analysis |
| 3 | Contextualize Supply-Chain Risk | external dependency risk bound to affected elements | IA | Ingest & Reconcile Supply-Chain Signals; Refresh Security Signals (new, §6.1) |
| 4 | Treat Risks & Track Compliance Obligations | risks dispositioned, obligations tracked | IA | Manage Risk & Compliance |
| 5 | Build & Seal the Assurance Case | tamper-evident, reviewable assurance case | IA, AAV | Build Assurance Case |

**VS-3 Grow Reusable Enterprise Knowledge**
| # | Stage | Value item | Serves | Realized by |
|---|---|---|---|---|
| 1 | Author Architecture Content in the Engagement | candidate reusable knowledge | AKM, ANC | Author Model Artifacts |
| 2 | Validate & Review Promotion Candidates | quality-assured promotion set | AAV, TKG | Validate Promotion Selection; Detect Promotion Conflicts |
| 3 | Promote to the Enterprise Tier | shared reviewed baseline grows | TKG | Promote Artifacts; Execute Promotion |
| 4 | Reuse Enterprise Knowledge Across Engagements | faster, consistent planning in other engagements | AKM, TKG | Compose Combined-Scope Read |

**VS-0 Adopt the Platform**
| # | Stage | Value item | Serves | Realized by |
|---|---|---|---|---|
| 1 | Discover & Evaluate the Platform | informed adoption decision | — | (documentation, not model behavior — deliberate gap, stated in the stage description) |
| 2 | Install & Configure the Platform | running, configured platform instance | AKM | Initialize Repository |
| 3 | Import Authoring Guidance | guidance-assisted authoring enabled | ANC | Load Guidance Content |
| 4 | Model the First Engagement | first architecture model delivering answers | AKM, ANC | Architecture Modelling & Planning (m:n with VS-1.1/1.2) |

Persona note: value/stakeholder associations use STK entities (§4.8). The "AI
Agent" persona exists only as a **role** (`ROL@1776633082.udXPfB`) — associate it
to VS-1 via the legal value-stream↔role association, do not create a duplicate
stakeholder.

### 4.8 Referenced existing artifacts (IDs — use these verbatim)

Processes: Architecture Modelling & Planning `PRC@1776635640.U4aAdh` · Architecture
Implementation `PRC@1776635645.GHVpDA` · Architecture Conformance Review
`PRC@1776635649.vlE-5j` · Reverse Architecture `PRC@1777293168.CYgU64` · Promote
Artifacts `PRC@1712870400.0Rz5Ex` · Initialize Repository `PRC@1776633074.Tz_a_O` ·
Conduct Hazard Analysis `PRC@1780656241.TfWiGw` · Manage Risk & Compliance
`PRC@1780656241.7YyhMi` · Build Assurance Case `PRC@1780656241.bWETd2`.

Functions: Author Model Artifacts `FNC@1777390448.yuFXVJ` · Index Repository
`FNC@1777390446.dxb6ru` · Verify Artifact Integrity & Coherence
`FNC@1777390445.NGjUCa` · Retrieve Architectural Context `FNC@1777390452.3seqIw` ·
Synthesize & Deliver Implementation Guidance `FNC@1777390454.4ce2Qt` · Refine
Architecture Content after Implementation `FNC@1777474430.fCdnJ2` · Validate
Promotion Selection `FNC@1777390498.54UnNB` · Detect Promotion Conflicts
`FNC@1777390497.ndMgDn` · Execute Promotion `FNC@1777390494.6xjXsw` · Compose
Combined-Scope Read `FNC@1783266393.4zLFys` · Ingest & Reconcile Supply-Chain
Signals `FNC@1780656241.0hyhf0` · Author Assurance Artifacts
`FNC@1780656241.snlj8X` · Load Guidance Content `FNC@1783870976.MlO3ST` · Graph
Traversal `FNC@1776633080.BdEMPx` · Check Model Coverage `FNC@1777390465.SXt2mM` ·
Author Diagrams `FNC@1777390449.uzJGYp` · Attribute Schema Validation
`FNC@1712870400.B_F-Sq`.

Stakeholders (STK, not the same-named ROL/ACT entities): Architect
`STK@1712870400.aB3dE1` · Developer `STK@1712870400.K9xTq2` · DevOps Engineer
`STK@1712870400.4oprPM` · Product Owner `STK@1712870400.Zp8Lm4` · Upper Technical
Management `STK@1712870400.Rr9Ss9` · Risk & Compliance Officer
`STK@1780655839.AsnqRa` · Safety / Security Analyst `STK@1780655839.r4P3gy`. Role:
AI Agent `ROL@1776633082.udXPfB`.

Motivation targets: OUT Increased Architectural Coherence `OUT@1712870400.LrpdG0` ·
OUT Assurance Analysis Surfaces Modeling Gaps `OUT@1780655839.Vhhne7` · OUT
Assurance Friction & Guidance Overhead Reduced `OUT@1780655839.CiC0ku` · OUT
Assurance Findings Traceable End-to-End… `OUT@1780655839._FOogJ` · OUT
Architectural Guidance Available Without Specialist Dependency
`OUT@1776629097.FXFGrO` · GOL Provide First-Class Assurance over the Architecture
Model `GOL@1780655839.AoatzG` · DRV AI-Assisted Development as Dominant Production
Mode `DRV@1776628131.GR9prv` · DRV Safety, Security & GRC Capability Gap for Small
Teams `DRV@1780655839.52-qYT` · PRI Extensibility and Configurability
`PRI@1712870400.uraDPR`.

Requirements: Tool Interfaces: MCP, CLI, REST `REQ@1712870400.peinbQ` · Assurance
to Architecture Linkage `REQ@1780655839.kjBJrh` · Two-Tiered Repository
`REQ@1712870400.kOU3al` · Promotion Mechanism to Enterprise Repository
`REQ@1712870400.Gg4Hh4` · External Supply-Chain Signal Ingestion
`REQ@1780655839.urjIeU` · Assurance Diagram Outputs and Sources Are
Classification-Gated `REQ@1781640247.cmI5m2` · Deployment-Level Guidance Import
`REQ@1783870978.mUf9JQ` · Configurable Model Attribute Schemata
`REQ@1712870400.6ZR3nk` · Repository Authoring Policy: Required Attribute Defaults
`REQ@1781886720.VJ2ml-` · GUI Exploration and Authoring for Humans
`REQ@1712870400.NfAmrl`.

Objects: BOB Enterprise Repository `BOB@1712870400.6Uok0b` · BOB Engagement
Repository `BOB@1712870400.so7gfN` · DOB Architecture Modelling Guidance
`DOB@1780656431.T8nsTi` · DOB Assurance Method Guidance `DOB@1780656431.NtsoOS` ·
DOB Assurance Knowledge Base `DOB@1780656431.ApaPcg` · DOB Bill of Materials
`DOB@1780656431.dRnK-o` · DOB Security Signals Store `DOB@1780656431.p04R7k` · DOB
Architecture Ontology Configuration `DOB@1777293139.UjyXG3`. Components: APP
Architecture Backend `APP@1777293133.OYEmP1` · APP GUI Authoring Tool
`APP@1776149382.lmO0mp` · APP Supply-Chain & Vulnerability Connector
`APP@1780656431.e2zPs6` · APP Query Binding Evaluator `APP@1784017469.RyUgp4` · AIF
Assurance REST Interface `AIF@1782080492.Y4n-FB`.

(IDs recorded 2026-07-19 from the live index; per the resume protocol, re-verify by
name lookup on any mismatch rather than improvising.)

### 4.9 Trace acceptance — named witness chains (replaces any single-query claim)

`element-dependents` is an incoming, certain-only, 4-hop-capped derivation that
**excludes associations** — so no single derived query can run component → persona
(the value/stakeholder hops are associations by design). Derivation rules are NOT
weakened to force this. Acceptance instead verifies two named witness chains,
hop by hop (each hop = one direct connection asserted via
`artifact_query_find_connections_for`, with type and direction):

- **W1 (component → capability, derivation-compatible):** hop 1:
  `Promotion Engine (APP@1776633693.tIMxjr)` —archimate-assignment→ `Execute
  Promotion (FNC@1777390494.6xjXsw)` *(new in WU-A1; verified absent at review
  time; semantically justified — the engine performs the function)*; hop 2:
  `Execute Promotion` —archimate-realization→ CAP `Tiered Knowledge Governance`
  *(new in WU-A1)*. Derived check, named exactly: the `element-dependencies`
  viewpoint (outgoing/dependency direction) rooted at `Promotion Engine`,
  max 4 hops, must include CAP `Tiered Knowledge Governance` (the assignment +
  realization chain composes in that direction). The direct hop-by-hop checks
  are kept even when the derived check passes.
- **W2 (behavior → stage → value → persona, association-terminated):** hop 1:
  `Promote Artifacts (PRC@1712870400.0Rz5Ex)` —archimate-realization→ VS-3 stage
  *Promote to the Enterprise Tier*; hop 2: **stored as** VS-3 parent
  —archimate-composition→ stage (the witness walks this connection from target
  to source); hop 3: VS-3 parent —archimate-association— VAL `Compounding,
  Reusable Architecture Knowledge`; hop 4: VAL —archimate-association— STK
  `Upper Technical Management (STK@1712870400.Rr9Ss9)` *(all new in WU-A2)*.

If a one-query component→persona projection is ever a real requirement, it is a
purpose-built trace projection combining relationship families explicitly — out
of scope here (§14).

## 5. Part B — Assurance connection explorability (GUI + REST)

### 5.1 Self-model delta

New/changed behavior (application domain, group `assurance`):

| Element | Type | Rationale & relations |
|---|---|---|
| Resolve Assurance Edge Endpoints | function (new) | Enriches edges with endpoint name/type under the exposure policy. Realizes REQ-B1 (below); assigned to APP `Architecture Backend`; serves the browse/detail surfaces via AIF `Assurance REST Interface`. |
| Traverse Assurance Neighbor Graph | function (new) | Bounded, cycle-safe, policy-filtered traversal. Realizes REQ-B1; accesses DOB `Assurance Knowledge Base`. |
| Serve Assurance Edge Catalog | function (new) | Serves connection types + pair legality from the assurance ontology module. Realizes REQ-B2; accesses DOB `Architecture Ontology Configuration` (the assurance module config is part of the module catalog). |
| Author Assurance Artifacts | function (existing) | Gains the server-side legality validation on edge create (no new entity; description updated). |
| Assurance Neighborhood Projection | data-object (new) | The transient traversal result served to the GUI (ephemeral; never persisted — description states this). Accessed by the new traversal function; realizes nothing in git. |

No new processes, business objects, or events (reads dominate; edge authoring reuses
the existing write path/event flow). Existing APP `Unified Assurance Diagram
Surface`, `Assurance Read Connection Pool`, `GUI Authoring Tool`, AIF `Assurance REST
Interface` gain serving/access connections to the new functions.

Motivation & strategy links:
- **REQ-B1 (new)** `Assurance Graph Exploration` — assurance connections are
  navigable (names, links, traversal, graph view), unlock-gated and exposure-policy
  filtered. Realizes OUT `Assurance Findings Traceable End-to-End to the Architecture
  Model`; refines the spirit of REQ `GUI Exploration and Authoring for Humans`
  (association); realized by the new functions.
- **REQ-B2 (new)** `Ontology-Driven Assurance Edge Authoring` — legal edge types are
  derived from the assurance ontology (single source), enforced server-side. Realizes
  OUT `Assurance Findings Traceable…` + PRI-adjacent association to `Extensibility
  and Configurability`.
- Strategy: both REQs are realized-support for CAP `Integrated Safety, Security &
  Compliance Assurance`; the analyst user tasks live in VS-2 stages *Analyze Hazards
  & Threats* and *Treat Risks & Obligations*.

### 5.2 Problem-domain dimensions & variations

Store state {unlocked, locked, not configured} × content TLP {node ≤ ceiling, node >
ceiling} × node degree {0, 1, many edges} × edge target {live node, dangling id,
above-ceiling node} × graph shape {tree, cycle (feedback loops are *by design* in
control structures), disconnected} × traversal depth {0, 1, max_hops, beyond} ×
pair legality {legal pair, illegal pair, pair with zero legal types} × direction
{outgoing, incoming} × deep link {valid id, unknown id, locked store} × session
transition {unlock→lock mid-session} × concurrency {node deleted while displayed}.

### 5.3 Invariants

- **I-B1 (global, confidentiality — omission, never redaction):** an edge is
  returned iff **both** endpoints are visible under the exposure policy — exactly
  the existing contract (`assurance_exposure.py`). No per-edge placeholders, no
  withheld-edge counts, no disclosure of an excluded endpoint's existence,
  connection type, or direction; traversal never crosses an excluded node (not
  even as a pass-through hop). The only permitted signal is a coarse, per-response
  `visibility_limited` policy-scope flag. Dangling-edge integrity findings surface
  only through the appropriately privileged verifier, never through ordinary
  navigation. Uniform across node-read, edge-list, neighbors, and search.
- **I-B2 (global):** every assurance REST response carrying confidential content has
  no-store semantics; nothing new is written to disk (extends the search-safety
  invariant/test pattern).
- **I-B3 (local):** traversal terminates on cyclic graphs (visited set), respects
  `max_hops` server-side bounds, and is deterministic for a given store state.
- **I-B4 (local):** an edge create violating `permitted_relationships` is rejected
  server-side with a typed error; GUI options are always a subset of server-legal
  options; the ontology file is the single source (no literal list remains in the
  frontend).
- **I-B5 (local):** locked store ⇒ all Part B endpoints return the locked status
  (423 semantics per existing policy); the GUI collapses to the locked state on its
  next fetch/navigation and fetches nothing new. No active purge machinery:
  content already on screen was shown to the person who unlocked the store, and this
  product's threat model is proportionate (see §11), not high-assurance
  confidentiality.
- **I-B6 (audit):** edge create and delete remain audited (existing append-only
  log) — no new mutation path bypasses it. (There is no edge-edit path and v1
  adds none — D6.)

### 5.4 Control structure & unsafe control actions

Controllers/paths: Analyst → GUI → REST (exposure policy) → application use cases →
store; ontology module → catalog endpoint → picker.

- **UCA-B1** *Name resolution provided* for an above-ceiling endpoint (leak by
  enrichment). [→ F2.1]
- **UCA-B2** *Traversal provided* across an above-ceiling node (leak by topology:
  existence + connectivity inferable). [→ F2.2]
- **UCA-B3** *Traversal provided too long* (unbounded on cyclic graph → resource
  exhaustion of the shared backend). [→ F2.3]
- **UCA-B4** *Edge create provided* for an illegal pair (graph integrity silently
  degraded; downstream STPA completeness checks reason over a malformed graph).
  [→ F2.5]
- **UCA-B5** *Confidential fetches continue* after lock occurs mid-session (new data
  served past the gate — the proportionate concern; already-rendered content is
  accepted residual exposure). [→ F2.7]

### 5.5 Failure modes with S|O|D

Scales — S(everity): 1 cosmetic … 7 wrong risk-relevant information … 9-10
confidentiality breach / unbounded outage. O(ccurrence): 1 hardly conceivable … 5
plausible in normal use … 8+ near-certain. D(etection): 1 caught by an existing
gate/test … 5 caught by attentive user … 9 silent until harm. RPN = S·O·D.

| ID | Failure mode | S | O | D | RPN | Primary mitigation |
|---|---|---|---|---|---|---|
| F2.1 | Edge enrichment leaks above-ceiling names or (via placeholders/counts) existence, type, or topology | 9 | 4 | 9 | 324 | I-B1 omission semantics (reuse the existing exposure predicate, never a new redaction path); policy unit matrix + REST integration matrix incl. mixed-TLP fixtures |
| F2.2 | Traversal crosses or reveals an excluded node | 9 | 3 | 8 | 216 | Per-hop omission; integration matrix incl. pass-through case |
| F2.3 | Cycle or dense breadth → unbounded traversal / oversized response / backend hang | 6 | 5 | 4 | 120 | Visited set + max_hops clamp + node/edge/time budgets with typed truncation (D7); unit + load test |
| F2.4 | GUI type list drifts from ontology (stays hardcoded / partial migration) | 4 | 6 | 6 | 144 | Delete literals; catalog endpoint from the loaded module; Vitest asserting options come from fetch; contract test endpoint == loaded module representation |
| F2.5 | Incomplete matrix becomes authoritative enforcement, breaking valid GRC/evidence/binding workflows | 7 | 8 | 7 | 392 | WU-B0 reconciliation BEFORE enforcement: the D6 handbook-validated matrix + verifier alignment + store preflight/repair land together; exhaustive enforcement only over the reconciled model (Q13) |
| F2.6 | Deep link to unknown/deleted node crashes view | 3 | 4 | 3 | 36 | 404 handling; e2e route walk |
| F2.7 | Fetches after mid-session lock still return confidential data | 5 | 4 | 4 | 80 | Server-side gate already refuses (423); GUI collapses on next fetch (natural path); one Vitest that a locked response clears panel state — no purge machinery, no dedicated e2e (proportionality, §11) |
| F2.8 | Dangling edge (deleted endpoint) leaks through navigation or breaks rendering | 4 | 3 | 5 | 60 | I-B1: omitted from navigation like any non-visible endpoint; surfaced as a privileged verifier finding only; unit test |
| F2.10 | A cross-architecture reference (e.g. binds-to) is enforced or stored as an assurance edge | 8 | 7 | 6 | 336 | D6 relationship-kind taxonomy; separate catalogs, mutation use cases, and preflights for edges vs arch refs (two-level negative tests) |
| F2.11 | Time-budget truncation produces non-repeatable results or contradicts determinism | 7 | 5 | 6 | 210 | D7: size budgets define partial results; time budget fails the whole request; no continuation tokens in v1 |

### 5.6 User scenarios, stories, expected behavior

- **Story B-S1 (analyst, explore):** *As a Safety/Security Analyst, from a hazard I
  follow its edges by name to losses, UCAs, and constraints so I can judge causal
  coverage.* Tasks: open node → read grouped, name-resolved edge lists → click
  through → breadcrumb back. Expected: every returned edge shows type badge +
  endpoint name + node-type and click navigates; edges to non-visible endpoints
  are absent entirely (I-B1), with at most a coarse `visibility_limited` note on
  the response.
- **Story B-S2 (analyst, graph):** *As an analyst I explore the control structure as
  a graph, expanding neighbors, to spot missing feedback paths.* Expected: canvas
  identical in interaction to the architecture explorer; expansion bounded; cycles
  render; locked store → next interaction shows the locked status and the view
  collapses.
- **Story B-S3 (analyst, author):** *As an analyst I connect a new loss-scenario to
  its UCA with only legal types offered.* Expected: picker offers exactly the
  matrix-legal types for the pair (both directions selectable); illegal submissions
  are impossible from the GUI and rejected by the server; created edge appears
  immediately, deletable from the detail view.
- **Story B-S4 (owner, report):** *As the owner I deep-link a node in a session
  note.* Expected: `/assurance/node/:id` resolves when unlocked; locked → status
  page, no existence leak for above-ceiling ids (same response as unknown id).
- **Overall outcome:** assurance connections reach parity of explorability with
  architecture connections; no confidentiality regression (I-B1/I-B2 hold under test).

### 5.7 Test strategy

| Level | Coverage (mapped to RPN) |
|---|---|
| Domain/application unit | Traversal (cycles, hops, node/edge budgets with typed truncation + frontier node IDs, whole-request time abort, multiedges/self-loops, deterministic ordering — F2.3/D7); exposure omission incl. pass-through and dangling endpoints (F2.1/F2.2/F2.8); matrix validation behind the WU-B0 decision (F2.5); YAML→module loading tested separately from the transport contract (F2.4). Separate test file per use case. |
| Backend integration (real SQLCipher store, seeded TLP mix) | REST matrix over §5.2 dimensions: enrichment × TLP, neighbors × locked/unlocked × ceiling, catalog == ontology, no-store headers, no-new-file assertion (extend the search-safety pattern) — covers F2.1/F2.2/F2.7 at the wire. |
| Frontend Vitest | Edge lists render links+names from payload (no id fallback when name present); picker options sourced from catalog fetch and filtered by pair (F2.4); a locked response clears panel state (F2.7 — the proportionate check). |
| Playwright e2e | Route-walk additions (`/assurance/node/:id`, graph view, locked-state route walk); story B-S1 click-through; B-S3 create-edge happy path. |

All RPN ≥ 100 modes get **both** a unit/application test and an integration or e2e
test; F2.1/F2.2 (S ≥ 8) additionally get explicit negative tests at two levels.

## 6. Part C — Security signals dogfooding & virtual viewpoint attributes

### 6.0 Normative operation & data contracts (locked)

**(a) Capability predicate over the FULL configuration space and audit
durability (D21).** "Audited" is a durable-state invariant: **no accepted
signal mutation may exist without its durable audit record committed in the
same unit of work.** The configuration space is the real factory cross-product
— store `sqlcipher | pocketbase | private-git` × signals
`sqlcipher-colocated | sqlite | encrypted` × archive
`standard | worm | s3-worm | azure-blob-worm` × lock state — not two
dimensions. **Signal mutations (refresh lifecycle, BOM/vuln/anchor, VEX) are
allowed iff:**

```text
store = sqlcipher AND signals = sqlcipher-colocated
AND archive ∈ {standard, worm}          # local, same-database → real transaction
AND unlocked
```

In exactly that combination, signal SQL and the audit-row SQL commit in ONE
SQLCipher transaction owned by the application unit of work — **existing
adapter methods that commit independently cannot be invoked inside it**
(refactor, don't wrap). Every other combination — cloud WORM archives
(`s3-worm`, `azure-blob-worm` are independent of the database; no atomic
boundary exists), `pocketbase`/`private-git` stores, plain-`sqlite` signals —
**denies mutations with a typed capability reason**; reads/metrics remain
available where exposure policy allows. The transactional ledger + cloud
delivery outbox is the documented future path for cloud-WORM writes (§14).
The `signals_backend=encrypted` alias resolves per store backend and is
**migrated explicitly** (§9.1): SQLCipher store → `sqlcipher-colocated`;
non-SQLCipher store → blocking owner-choice finding. Configurations that lose
write capability under this predicate produce an explicit upgrade finding —
never silent read-only degradation. Fault-injection acceptance covers every
allowed AND denied archive combination at every commit boundary (before signal
commit; inside the transaction; after commit; duplicate retry; archive
locked/unavailable mid-operation), asserting mutation-with-audit or no
mutation, and idempotent recovery without duplicate audit events.

**Public SQLite (Q10, option 1 — honest deprecation):** `signals_backend=
sqlite` is **deprecated for metrics in v1**. It has no population path (writes
denied; quarantine leaves no active run; a fresh file has nothing), so
advertising it would promise metrics it cannot produce, and the current SQLite
adapter is writable (creates directories/tables) — prose cannot make it
read-only. Upgrade emits a finding with instructions to select co-located
SQLCipher for refresh/metrics; legacy public rows above TLP:WHITE block or
quarantine (never remain readable because old code treated TLP as
informational); an absent public file is `unavailable/no snapshot`, never
silently initialized. D11's "public backend preserved" claim is **withdrawn**;
docs/tests/demos use co-located only. The atomic TLP:WHITE
snapshot-publication command is the documented future path if a public
read-only deployment becomes a real requirement (§14).

**(b) Refresh orchestration = one application command.** A single
`RefreshSecuritySignals` application command owns: typed refresh-bundle
validation (anchor + normalized SBOM + acquisition results + diagnostics +
source/generator metadata), beginning a unique staging run, populating
components/aliases/vulnerability records/findings under that run, marking
complete only when all required data is present, atomic activation, failure
recording with safe diagnostics, and the audit event per (a). Low-level
transition methods exist only on the store port. **v1 exposes this command via
the CLI/script adapter only — deliberately no public REST/MCP lifecycle API**
(adapters can be added later against the same use case). The script generates
SBOMs and acquires OSV data, then submits the bundle; an architecture/dependency
test proves it imports no infrastructure connector.

**(c) Run lifecycle, identity, concurrency, retention.**
- Lifecycle: `staging → complete → active → superseded` and `staging → failed`;
  status plus `activated_at`/`superseded_at` timestamps (never overloading one
  field). A run activates only from `complete`; re-activating the same `run_id`
  is a no-op success.
- Identity & idempotent replay (failed is TERMINAL — replay returns, never
  resumes): every execution creates a unique `run_id`.
  `IdempotencyKey = (anchor_entity_id, request_id)` — per-anchor scope, the
  natural aggregate boundary since one bundle has exactly one anchor; a
  multi-anchor script generates a distinct `request_id` per command.
  `request_payload_digest = SHA-256(canonical accepted RefreshBundle)` — every
  semantic field after normalization (components, findings, aliases,
  applicability evaluations, diagnostics, generator/source metadata, anchor),
  excluding only generated fields (run id, timestamps). Deliberately NOT the
  BOM digest (BOM content is not the whole command); both persist separately
  as idempotency vs provenance fields. Normative transition table:

  | Existing key | Digest | Stored outcome | Result |
  |---|---|---|---|
  | none | any | none | create a new staging run |
  | same key | same | staging | return "in progress, retry later"; no mutation |
  | same key | same | active/superseded | return stored success (original run id); no mutation, no new audit |
  | same key | same | failed | return stored failure + "use a new request_id"; no mutation, no new audit |
  | same key | different | any | **typed idempotency conflict; no signal or audit write** |
  | new request_id | same payload | any prior run | create a new audited run |

  Tested at domain AND real-SQLCipher integration level, incl. canonicalizable
  input reordering (same digest), semantic field change (different digest →
  conflict), and concurrent duplicate calls.
- Activation is one database transaction (supersede previous active + activate
  target); **one active run per anchor is a database constraint**, and
  creation/activation serialize through the existing write queue — process-local
  locking alone is insufficient.
- Stale staging recovery: marked failed after an explicit timeout at the next
  refresh or via admin repair; never auto-activated.
- Retention (v1): **no automatic deletion** — run history is exposed, growth is
  documented, pruning is out of scope (§14).
- Migrations and invariant tests run against BOTH public SQLite and co-located
  SQLCipher adapters.

**(d) Contextual VEX contract.** Key:
`(anchor_entity_id, canonical_component_id_incl_version, canonical_vulnerability_id)`
— run-independent; it applies exactly when a run contains that
component/version/vulnerability finding; **no carry-over to any other component
version**. Assessments are immutable revisions with one current revision per key
(latest-valid precedence; superseded revisions retained). Dispositions:
`affected | not_affected | fixed | under_investigation`; only `not_affected` and
`fixed` suppress an open finding, and both **require a justification**;
author/timestamp/source recorded; every revision is an audited mutation. Alias
merges update the internal vulnerability identity without losing assessment
history. **Visibility is evaluated before suppression**: a VEX revision the
caller cannot see never silently suppresses a finding the caller can see.

**(e) Filter-before-aggregate and closed result states.** The exposure policy is
applied to components, findings, severity records, and applicable VEX revisions
**before** any count, maximum, band, or classification is computed;
classification = maximum of **visible** contributors; no total is ever computed
from hidden rows; all-hidden ⇒ an empty, `visibility_limited` projection — never
"zero vulnerabilities". Result carries two closed fields: availability
`available | unavailable` and content state
`complete | visibility_limited | no_active_run | no_findings`. Payload always
includes `finding_total`, `applicability_unknown_count`,
`unknown_severity_finding_count`, `component_count`, per-directness
`open_component_findings`, `distinct_open_vulnerabilities`, `max_cvss_score`,
`max_severity_band`, basis `run_id` + timestamp, and computed classification.
Severity-band counts are **component findings**; distinct-vulnerability counts
are named separately. `visibility_limited` stays coarse (ceiling below maximum
supported class — never a withheld-row count). Mixed-TLP property tests must
fail if a hidden row influences any count, maximum, band, suppression, or
classification.

**(f) Snapshot token.** One application capability call returns an opaque
`SignalSnapshotToken` covering: connector/backend identity, availability
revision, active `run_id`/revision, exposure ceiling/config revision, and VEX
revision. Batch reads happen under one token and the token is revalidated before
return; on any revision change the result is `unavailable/retry` — never partial
values. The SQLCipher connection manager's internal generation is exposed
through an inward-facing availability-state port (or a composition-owned
revision bumped on lock/unlock/reconfigure); the viewpoint application layer
never imports the connection manager.

**(g) Deterministic identity, applicability, scoring, directness.**
- Alias identity: an internal immutable vulnerability ID + a unique alias table
  (never a mutable "smallest external alias" primary key); linking two existing
  canonical groups merges transactionally with history preserved.
- Finding uniqueness: one canonical vulnerability × exact component/version ×
  anchor × run = exactly one finding, however many OSV affected entries or query
  responses support it; all provenance retained separately.
- OSV input validity: queries use valid versioned package identities; malformed
  or versionless components go to explicit unmatched/applicability-unknown
  diagnostics, never silently dropped.
- Affected ranges: ecosystem-specific comparison adapters; event semantics for
  `introduced`/`fixed`/`last_affected`/`limit`; commit events recorded as
  provenance only (not evaluated) in v1.
- CVSS: a short dependency-selection spike with acceptance criteria — CVSS
  2.0/3.0/3.1/4.0 vector support, agreement with official vector fixtures,
  acceptable license, strict invalid-vector behavior. Invalid vectors increment
  unknown severity, never crash and never score 0. Multiple severities per
  vulnerability: select the maximum valid applicable score, preserving vector,
  nomenclature, source, and selection provenance. `max_cvss_score` = locally
  computed from upstream-reported vectors/scores, never synthesized from a band.
- Directness: the root is not a dependency; depth 1 = direct; reachable depth
  ≥ 2 = transitive; unreachable/missing/cyclic-invalid = unknown; cycle handling
  terminates deterministically.
- New purl/CVSS dependencies are an immediate full-gate event with license,
  maintenance, official-fixture accuracy, and lockfile review.

**(h) Vocabulary & tooling.** `assurance_security_stats` reports run counts by
status, active runs per anchor, component and finding totals (units named), and
excludes failed/superseded runs from posture figures while reporting their
counts. **Anchor terminology:** the run's `anchor_entity_id` (product
architecture anchor) is distinct from the pre-existing component-level
`anchor_mappings` (retained for AI-BOM/component reconciliation; they can never
change run attribution). Tooling prerequisites documented in E1: npm ≥ 9.5
(`npm sbom`), the pinned cyclonedx-py generator, and generator versions recorded
into run provenance.

### 6.1 Self-model delta

| Element | Type | Rationale & relations |
|---|---|---|
| Refresh Security Signals | process (new) | Causally ordered: generate SBOMs → ingest BOMs → query & import vulnerabilities → verify stats. Assigned: ROL `AI Agent` / ACT `DevOps Engineer`. Realizes VS-2 stage *Contextualize Supply-Chain Risk*; serves REQ `External Supply-Chain Signal Ingestion` (realization). Triggers EVT below. |
| Compute Security Posture Metrics | function (new) | The single metrics use case (D9). Realizes REQ-C1; accesses DOB `Security Signals Store`; assigned to APP `Supply-Chain & Vulnerability Connector`. |
| Provide Signal-Derived Viewpoint Attributes | function (new) | The provider-port behavior consumed by viewpoint evaluation (D10). Realizes REQ-C1 + REQ-C2; serves APP `Query Binding Evaluator`; accesses nothing persistent beyond the metrics function (serving relation to it). |
| Security Refresh Run | data-object (new) | The atomic ingest aggregate (D9): staged/complete/failed runs with component and vulnerability findings, activation state, retention. Accessed by the refresh process and the metrics function. |
| Security Posture Metrics | data-object (new) | Computed, transient aggregate (distinct vulnerabilities, component findings by directness, severity bands, `max_cvss_score`, classification, basis run) — description states: never persisted, never exported outside the D11 pipeline. Accessed (read) by the provider function. |
| Assess Vulnerability Applicability | function (new) | The audited, contextual VEX assessment behavior (disposition + justification per anchor/component/vulnerability). Realizes REQ-C1's VEX clause; assigned to APP `Supply-Chain & Vulnerability Connector`; serves the analyst via AIF `Assurance REST Interface`. |
| Security Signals Refreshed | event (new) | Raised on successful activation of a refresh run; triggers nothing yet (verification/reporting hook later). |
| Bill of Materials / Security Signals Store | data-object (existing) | Unchanged; gain access connections from the new process. |

Motivation & strategy links:
- **REQ-C1 (new)** `Entity-Level Security Posture Metrics` — per-architecture-entity
  VEX-effective metrics derived from anchored BOM components and vulnerability
  records, computed on demand, unlock-gated, **and visible where architecture
  decisions are made**: viewpoint styling (D10) and a read-only derived-attributes
  panel on the entity detail page (D17). Realizes OUT `Assurance Findings
  Traceable End-to-End to the Architecture Model`; serves GOL `Provide First-Class
  Assurance over the Architecture Model`. GUI surface: `GUI Authoring Tool` gains a
  serving connection from `Compute Security Posture Metrics` via AIF `Assurance
  REST Interface` (no new self-model entity — the panel is presentation of the
  same function).
- **REQ-C2 (new, constraint specialization)** `Signal-Derived Styling Never
  Persisted` — viewpoint styling sourced from security signals is ephemeral,
  unlock-gated, and refused in any git-persisted artifact; user-initiated downloads
  carry a TLP banner + timestamp (D11). Refines REQ `Assurance Diagram Outputs and
  Sources Are Classification-Gated` (association/refinement); realized by the
  create/edit-diagram refusal and the banner-stamped export path.
- **REQ-C3 (new, status: draft)** `Exploitability-Informed Vulnerability
  Prioritization` — planned, not implemented: enrich per-entity metrics with an
  exploitability signal (EPSS or equivalent feed) so treatment ordering reflects
  likelihood, not only severity. Draft status records intent per Q1; association →
  REQ-C1 and GOL `Provide First-Class Assurance over the Architecture Model`. No v1
  realization connections (requirements-coverage views will correctly show it as an
  open gap).
- Strategy: the whole part realizes CAP `Integrated Safety, Security & Compliance
  Assurance` and VS-2 stage 3; the dogfooding act itself realizes COA `Dogfood via
  the Recursive Self-Model`.

### 6.2 Problem-domain dimensions & variations

Run lifecycle {staging, complete+active, complete+superseded, failed, crash before
activation, overlapping runs same anchor, feed returns fewer records than prior
run, same serial different digest} × BOM format {CycloneDX, SPDX} × component
{unique package, same package under both anchors, no package identity} ×
vulnerability {vector-scored, band-only, neither, alias pair (CVE+GHSA),
version-qualified range match/miss, version-unqualified (applicability_unknown),
paginated batch result} × VEX {affected, not_affected, fixed, under_investigation,
absent} × VEX key {this anchor, other anchor, superseded component version} ×
directness {direct, transitive, unknown — dependency graph present/absent/
malformed, root ambiguous} × classification {all GREEN, mixed with RED, public
sqlite backend} × store {unlocked, locked,
signals empty, assurance module disabled deployment} × entity {anchored, unanchored,
anchor to since-deleted arch entity (dangling — tolerated per register contract)} ×
viewpoint {signal attribute in style only (deferred), in criteria (eager), both;
scale bands vs range tokens} × render path {GUI ephemeral, persisted diagram
(refused), export/exchange (excluded)} × scale {≈300 backend + ≈400 frontend
components, thousands of vulns}.

### 6.3 Invariants

- **I-C1 (global, one-way rule):** no **operational / live-store-derived** signal
  value is ever written under any repository path — not as entity properties, not in persisted rendered diagrams,
  not in exchange documents, not in logs above redaction policy. Tracked
  **synthetic** documentation fixtures are permitted solely through I-E1–I-E3
  (visibly marked, harness-proven origin). (Extends the no-plaintext invariant;
  test-enforced.)
- **I-C2 (global, atomic basis):** metrics are a pure, deterministic function of
  (one active completed refresh run per anchor, the contextual VEX assessments,
  one exposure-policy snapshot, D12 policy). Activation is atomic: a crash at any
  point leaves the previous run active; staging/failed runs are never readable as
  metrics basis; two consecutive evaluations without an intervening activation or
  VEX/policy change are identical.
- **I-C3 (local, contextual VEX):** VEX suppression applies only within its
  exact §6.0(d) key — a disposition
  for one anchor or component version never suppresses another's finding — and is
  applied identically in the metrics tool, REST, dashboard, and provider (one use
  case, cross-surface consistency test). Every VEX change is an audited mutation.
- **I-C4 (local, backend-sensitive per the §6.0(a) predicate):** whenever the
  predicate says reads are unavailable (disabled backend; co-located while
  locked; no active run; deprecated public backend ⇒ `no_active_run`), the
  capability returns an explicit `unavailable`/`no_active_run` result ⇒
  viewpoint renders with default styling and a "signals unavailable" legend
  note — never an error, never a partial mix.
- **I-C5 (local):** findings scope by (run, anchor): a package shared by backend
  and frontend yields independent findings per anchor; no cross-anchor bleed and
  no bleed across runs.
- **I-C6 (local):** severity accounting partitions: every open finding is exactly
  one of {vector/score-backed, band-only, unknown}; `max_cvss_score` derives
  only from the first class, `max_severity_band` from the first two;
  `unknown_severity_count` and `applicability_unknown` counts are user-visible.
- **I-C7 (write-path):** BOM/vuln/anchor/VEX/run writes are unlock-checked and
  audited on the same path as other assurance mutations.
- **I-C8 (local):** styled output leaves the browser only through the D11 export
  pipeline (POST, in-memory, `Content-Disposition`, banner = computed
  classification + basis run + timestamp); no server-side files, and the persisted
  diagram download route is never used for signal-styled content.
- **I-C9 (local, units):** directness classification is total (direct | transitive
  | unknown) and per-class `open_component_findings` sum to the finding total;
  `distinct_open_vulnerabilities` is alias-deduplicated and is NOT claimed to
  partition by class.
- **I-C11 (local, snapshot coherence):** one viewpoint execution or metrics
  request pins one `SignalSnapshotToken` (§6.0(f)) and is all-or-none — a lock, unlock, policy change, or activation during evaluation
  yields either the pinned coherent snapshot or `unavailable`, never a mix.
- **I-C10 (local):** derived attributes on the entity detail page (D17) are fed by
  a payload disjoint from the editable properties model: they appear in no edit
  form state, no save payload, and no entity file after any edit round-trip; the
  panel is gated identically to the assurance lens (locked/absent/empty → hidden).

### 6.4 Control structure & unsafe control actions

Loops: (1) refresh script → `RefreshSecuritySignals` command (§6.0(b)) → store port → signals store; (2)
viewpoint evaluation → provider port → metrics use case → store; (3) analyst → GUI
render → decision about dependency risk.

- **UCA-C1** *Styled render provided* into a persisted/committed artifact (D11
  violated — confidential derivative in git). [→ F3.1]
- **UCA-C2** *Metrics provided* attributed to the wrong entity (wrong anchor at
  ingest, or cross-anchor bleed) — analyst treats the wrong component as risky/safe.
  [→ F3.2]
- **UCA-C3** *Metrics provided with stale/partial basis* (half-completed refresh run
  visible mid-ingest; or provider mixing locked/unlocked states). [→ F3.4/F3.8]
- **UCA-C4** *VEX suppression applied too broadly* (a `fixed` status suppresses a
  still-affected version) or *not applied* (alarm fatigue → real criticals ignored —
  hazard of the human loop). [→ F3.3]
- **UCA-C5** *Score mapping not provided* for unscored vulns (silent zero →
  understated max CVSS). [→ F3.5]
- **UCA-C6** *Provider wired* in an assurance-disabled composition (boot failure /
  import of assurance modules where the family is opt-out). [→ F3.9]

### 6.5 Failure modes with S|O|D

| ID | Failure mode | S | O | D | RPN | Primary mitigation |
|---|---|---|---|---|---|---|
| F3.0 | Incorrect OSV/purl/CVSS interpretation produces materially false posture metrics (mis-mapped batch results, unpaginated reads, alias double-counting, wrong affected-range, fabricated scores) | 9 | 7 | 8 | 504 | D12/D13 semantics: two-phase OSV with result↔component mapping + pagination; purl library; affected-range evaluation; alias canonicalization; scores only from parsed vectors; fixture-based permutation tests over each rule |
| F3.1 | Signal-styled render persisted to git (incl. via the persisted diagram download route) | 10 | 3 | 9 | 270 | D11 refusal by viewpoint semantics + dedicated render/export pipeline; test: persisted artifacts contain no signal values; repository-scan regression |
| F3.2 | Findings attributed to wrong entity (anchor confusion / cross-anchor or cross-run bleed) | 7 | 4 | 6 | 168 | I-C5 (run, anchor) scoping in the single use case; unit matrix with shared packages; refresh script asserts anchor ids against the model |
| F3.3 | Globally-scoped VEX suppresses another anchor's/version's finding, or suppression targets a superseded component version | 9 | 6 | 8 | 432 | Contextual VEX keying (D9) + audited VEX mutation; unit matrix incl. superseded-version case (I-C3) |
| F3.4 | Non-atomic refresh observable: crash between staging and activation, overlapping refreshes for one anchor, or feed shrinkage silently retiring nothing | 9 | 6 | 8 | 432 | Refresh-run aggregate + atomic activation (I-C2); single-writer serialization per anchor; run-scoped findings make retirement structural (absent from new run = not open); crash/overlap/shrinkage integration tests |
| F3.5 | Band-only or unscored records distort `max_cvss_score` (fabricated or silently dropped) | 6 | 5 | 6 | 180 | D12: no fabrication; band/score/unknown partition (I-C6) with visible unknown counts; permutation tests |
| F3.6 | Locked store / no active run breaks viewpoint rendering entirely | 4 | 6 | 3 | 72 | I-C4 `unavailable` fallback; unit + e2e locked render |
| F3.7 | Version-unqualified vulnerability identifiers treated as affecting all versions (or silently dropped) | 6 | 5 | 7 | 210 | D12 `applicability_unknown` class, surfaced separately; unit matrix over purl/range permutations |
| F3.8 | Same BOM serial with different content, or unstable generated serials, mislead run provenance | 5 | 5 | 6 | 150 | Run identity = `run_id` with caller `request_id` retry semantics (§6.0(c)); digest and serial are provenance only; test with mutated same-serial fixture |
| F3.9 | Assurance-disabled deployment breaks composition, or a locked-at-startup backend never gains the capability | 6 | 5 | 4 | 120 | D10 configured/null capability with per-call availability — never unlock-time injection; no-assurance boot test + lock-cycle integration test |
| F3.10 | Metric name collision with user-defined derived attributes | 3 | 3 | 4 | 36 | Names are viewpoint-author-chosen; validation rejects duplicate names already — add source-mix case |
| F3.11 | Dependency graph absent/malformed (or bom-ref/root discarded at parse) → wrong direct/transitive split | 5 | 6 | 5 | 150 | Parser preserves bom-ref/root/graph (D13); I-C9 `unknown` class (never guess); unit matrix over graph permutations |
| F3.12 | Exported render missing or under-stating classification (hardcoded AMBER over RED contribution) | 7 | 4 | 6 | 168 | D11 computed classification in payload + banner from payload; tests over co-located TLP-mix fixtures + explicit public-backend `unavailable/no_active_run` test |
| F3.13 | Derived attributes leak into the editable properties model → an edit persists them into the entity file | 8 | 3 | 7 | 168 | I-C10 structural separation (own payload + read-only component); regression test: edit round-trip on a metric-bearing entity leaves the entity file byte-identical in its properties |
| F3.14 | Derived-attributes panel rendered while the store is locked | 6 | 3 | 5 | 90 | Same gating path as the assurance lens (single helper); integration test locked→absent |
| F3.15 | Snapshot incoherence: values from before and after a lock/activation/policy change mixed in one render | 8 | 6 | 7 | 336 | I-C11 + §6.0(f) snapshot token, all-or-none; concurrency integration test flipping lock/run mid-evaluation |
| F3.16 | Signal mutation commits but its audit record does not (split-store partial write) | 9 | 5 | 8 | 360 | D21: mutations only on the co-located backend with data + audit in ONE transaction; public SQLite read-only; fault-injection at every commit boundary (two levels) |
| F3.17 | A store×signals×archive combination outside the §6.0(a) predicate accepts a mutation without an atomic audit boundary (e.g. cloud WORM archive) | 10 | 5 | 8 | 400 | Capability predicate enforced in the one unit of work; tests over standard/worm/s3-worm/azure-blob-worm and the encrypted alias; typed denial reasons |
| F3.18 | Hidden rows influence aggregate counts, maxima, bands, suppression, or classification | 9 | 4 | 8 | 288 | §6.0(e) filter-before-aggregate; mixed-TLP property tests (two levels) |
| F3.19 | Retained refresh runs grow the store without an operational policy | 5 | 6 | 6 | 180 | §6.0(c) explicit retain-all v1 decision; run history exposed in stats; growth documented (E1) |

### 6.6 User scenarios, stories, expected behavior

- **Story C-S1 (owner, refresh):** *As the owner I refresh security signals before a
  release.* Tasks: run the script → review its report (components, matched vulns,
  unmatched purls, unknown-severity count) → `assurance_security_stats` reflects
  the new active runs. Expected: a re-run creates a fresh run and atomically
  supersedes the previous one; retrying a failed request (same `request_id` +
  digest) returns the original failure and instructs a new `request_id`;
  partial acquisition failure fails the staging run
  with diagnostics and leaves the previous active run as the sole basis
  (F3.0/F3.4).
- **Story C-S2 (analyst, dashboard + VEX):** *As an analyst I open the supply-chain
  view and see per-anchor posture* (backend vs frontend), drill into the finding
  list, and record a VEX assessment (disposition + justification) for a false
  positive **scoped to that anchor/component/vulnerability** through the audited
  VEX mutation (use case + REST + GUI form); the metric updates on next
  evaluation, other anchors' findings are untouched, and the assessment appears in
  the audit log. Expected: numbers equal the MCP tool's output (I-C3).
- **Story C-S3 (analyst/architect, colored viewpoint):** *As an architect I apply a
  "security posture" viewpoint over an application view and see Architecture Backend
  and GUI Authoring Tool colored by max CVSS with a scale legend.* Expected:
  unlocked → colors + legend; locked → same diagram, default styling, "signals
  unavailable" note; attempting to save the styled diagram as a git artifact is
  refused with the classification message; downloading it produces a PNG/SVG with
  the computed classification, basis run, and timestamp (C-S3 is the acceptance
  demo for D10/D11).
- **Story C-S4 (architect, entity details):** *As an architect on the Architecture
  Backend's detail page with the store unlocked, I see its derived security
  attributes (distinct open vulnerabilities, component findings by directness,
  severity bands, max CVSS score, component count, basis run + timestamp) as
  read-only values on an offset background with the computed classification
  icon.* Expected: values equal the metrics tool's output (I-C3); the
  panel offers no edit affordance and nothing of it appears in the edit form;
  locked store → panel absent; entity without anchors → panel absent.
- **Overall outcome:** the self-model's backend/frontend carry live, truthful,
  confidential-by-default security posture, visible exactly where architecture
  decisions are made, with zero possibility of repository leakage.

### 6.7 Test strategy

| Level | Coverage (mapped to RPN) |
|---|---|
| Domain/application unit | D12 package-identity/range/severity permutation matrices incl. aliases and applicability_unknown (F3.0/F3.5/F3.7); contextual VEX keying incl. superseded-version and cross-anchor cases (F3.3); (run, anchor) scoping (F3.2); directness incl. graph permutations and finding-sum property (F3.11/I-C9); run lifecycle state machine + determinism (F3.4/I-C2); capability unavailable-fallback + deferral interplay (F3.6); snapshot-tuple pinning (F3.15/I-C11); style-rule integration with scale bands. |
| Backend integration (seeded SQLCipher signals) | End-to-end: fixture CycloneDX + OSV records → staged run → atomic activation → MCP metrics tool == REST == provider (I-C3 cross-surface test); crash-before-activation and overlapping-run tests (F3.4); feed-shrinkage retirement; VEX mutation audited (I-C7); unlock gating (locked → 423 / unavailable); lock-cycle after locked startup (F3.9); classification computation over co-located TLP-mix fixtures + public-backend `no_active_run` test (F3.12); no-new-plaintext-file assertion around evaluation & render. |
| Persistence refusal | Dedicated tests: create/edit-diagram with a signal-sourced viewpoint is rejected; saved artifacts and exchange exports contain no metric values (F3.1, two levels: use-case unit + integration over the real write path). |
| Script test | Refresh script dry-run mode against fixtures (no network in CI); OSV two-phase acquisition: pagination, result↔component mapping, GET fan-out dedup/retry/timeout, partial-source reporting (F3.0); staging-then-activate property (activation only after a fully staged run). |
| Frontend Vitest | Dashboard renders metric payloads; locked-state legend note; derived-attributes panel read-only rendering + absence from edit-form state (F3.13/I-C10); panel gating states (F3.14). |
| Playwright e2e | C-S3 demo: unlocked colored render (assert style tokens present) → simulated lock → default render + note; export download asserts banner + timestamp (F3.12/I-C8); supply-chain dashboard smoke. |

F3.1 (S=10) gets negative tests at two independent levels plus a repository-scan
regression; every RPN ≥ 140 mode gets unit + integration coverage.

## 7. Part D — Guidance pluralism & shipped modelling defaults

### 7.1 Self-model delta

| Element | Type | Rationale & relations |
|---|---|---|
| Layered Modelling Guidance | requirement (new) | Guidance is attachable to any hierarchy level an ontology module declares (for archimate-4: domain, entity type, specialization) and composed additively along the concept's ancestry path when authoring support is requested (D15). Realizes OUT `Architectural Guidance Available Without Specialist Dependency`; association → REQ `Deployment-Level Guidance Import`; realized by `Load Guidance Content` (function, description extended). |
| Shipped Default Attribute Schemata | requirement (new) | The product ships sensible default attribute schemata (incl. per-specialization overlays and the two unified enums) into new and existing repos without overwriting user files (D16). Realizes OUT `Architectural Guidance Available Without Specialist Dependency`; associations → REQ `Configurable Model Attribute Schemata`, REQ `Repository Authoring Policy: Required Attribute Defaults`; realized by `Attribute Schema Validation` (function, description extended: specialization overlay resolution) and the workspace initializer. |

Both requirements support CAP `Architecture Knowledge Management` and CAP
`Agent-Native Architecture Collaboration` (guidance and schemata serve humans and
agents through the same surfaces). No new processes/objects/events — the behavior
extends `Load Guidance Content`, `Attribute Schema Validation`, and the existing
initializer path.

Format sketch (v2, illustrative — the authoritative level declaration lives in the
module registry, never in the document):

```yaml
guidance_format: 2
meta_ontologies:
  archimate-4:
    domains:                      # a level archimate-4 declares
      strategy:
        context: >-
          Value streams and capabilities express the business model,
          organization-independently; processes and functions express the
          operating model of the concrete product. ...
    entity_types:                 # v1 slots, unchanged
      capability:
        create_when: ...
        never_create_when: ...
        specializations:
          some-slug: {create_when: ..., never_create_when: ...}
```

A module declaring a different tree (e.g. an assurance level `concern_classes`)
would use its own declared key in place of `domains` — the parser knows only
"declared level → nodes → context", nothing ArchiMate-specific.

**Hierarchy model contract (must be defined before parsing/serving code):**
- `GuidanceLevelId`: a **validated string** checked against the owning module's
  registry declaration — deliberately NOT a compile-time closed union, which would
  defeat module extensibility; plus a human-readable label and a total ordering.
- Node identity per level; parent relationship and ancestry resolution; validation
  for uniqueness, missing parents, and cycles (import-time errors, not runtime
  surprises).
- How entity types and specializations map into the tree (they are the two leaf
  levels; declared broader levels sit above them).
- Deterministic serialization of the composed result; defined behavior for
  disabled modules (their guidance is dormant, not an error).
- **Scope for this effort: registered `OntologyModule`s only** (archimate-4,
  assurance, …). Diagram-type modules do not participate yet; extending to them
  later happens via an explicit guidance-owner protocol, not by widening this
  implementation.
- **Canonical v2 wire shape (exactly one):** broader declared levels appear as
  top-level maps keyed by their declared level key (e.g. `domains:`); entity
  types and specializations stay in the v1 nested
  `entity_types`/`connection_types` slots, which the parser **adapts** into the
  two leaf hierarchy levels. There is no generic `levels:` map in documents; v1
  input is preserved unchanged.
- **Registry-kind behavior test:** disabled `OntologyModule`s produce dormant
  guidance; `DiagramTypeModule`s are ignored entirely.
- **Environmental prerequisite made explicit:** the extract at
  `~/.arch-guidance-extract/` is licensing-separated and absent from a fresh
  session. WU-D1 therefore (a) uses portable, redacted guidance fixtures for all
  tests, and (b) ends with an **owner checkpoint** for the real-extract
  restructure + re-import — completion of the WU never silently depends on the
  private file.

### 7.1b Normative schema payloads (exact persisted keys)

Property keys follow the existing display-key convention (`Maturity`-style) with
one deliberate exception: `investment_level` is lowercase because the shipped
resource-map style rule binds that exact key. Every schema: `$id` = filename,
`required: []`, `additionalProperties: true`. Two single-source constants
referenced by every using schema (defined once in the defaults module):
`SENSITIVITY_ENUM = ["Public", "Internal", "Confidential", "Strictly Confidential"]`
(description documents the TLP mapping WHITE/GREEN/AMBER/RED) and
`LIFECYCLE_STATE_ENUM = ["Planned", "In Development", "Active", "Deprecated",
"Retired"]`.

| File | Property key (title) | Type | Enum/format | Description must state |
|---|---|---|---|---|
| `attributes.resource.schema.json` | `investment_level` ("Investment Level") | integer, min 1, max 5 | — | band meanings: 1 minimal upkeep · 2 sustaining · 3 steady investment · 4 growth focus · 5 primary focus |
| `attributes.business-object.schema.json` | `Meaning` | string | — | what the object means to stakeholders |
| | `Provenance` | string | — | where the content originates |
| | `Contained Information` | array of string | — | information items carried |
| | `Internal Consistency Criteria` | array of string | — | criteria within one instance |
| | `External Consistency Criteria` | array of string | — | criteria against other objects/systems |
| | `Sensitivity` | string | SENSITIVITY_ENUM | planner-friendly; TLP mapping |
| | `Lifecycle States` | array of string | — | states an *information object instance* passes through — explicitly distinct from the component-level `Lifecycle State` enum |
| `attributes.application-component.service.schema.json` | `Programming Languages & Versions` · `Frameworks & Versions` · `Runtime Environments` · `Communication Protocols & Versions` | array of string each | — | one entry per item incl. version |
| | `Owner` | string | — | responsible party |
| | `Source Repository` | string | `format: uri` (informative — validator runs no format checker; stated in description) | where the code lives |
| | `Lifecycle State` | string | LIFECYCLE_STATE_ENUM | portfolio lifecycle stage |
| `attributes.application-component.module.schema.json` | `Problem Domain` | string | — | the domain the module addresses |
| | `Lifecycle State` | string | LIFECYCLE_STATE_ENUM | as above |
| `attributes.application-component.endpoint.schema.json` | `Communication Protocol & Version` | string | — | e.g. "HTTP/1.1 + SSE" |
| | `Authentication Method` | string | — | how access is guarded |
| | `Lifecycle State` | string | LIFECYCLE_STATE_ENUM | as above |

**Dogfood values are discovered, never invented:** the Architecture Backend's
Service attributes come from `pyproject.toml` (languages, frameworks), the
runtime configuration (runtime environments, protocols), and the actual
repository URL; the executor records the source of each value in the WU-D2
evidence. WU-D2 asserts the persisted JSON payloads structurally, not merely
that fields render.

### 7.2 Dimensions & variations

Guidance: document format {1, 2} × module {archimate-4, assurance, a
fixture OntologyModule declaring a different tree depth} × level {each level the module
declares — for archimate-4: domain, type, specialization; for a module declaring
fewer/more levels, exactly those} × node {known, unknown, level itself undeclared
by the module} × import mode {strict, lenient} × serving context {type guidance
request, domain-filtered request}.
Schemata: resolution {type only, type+specialization overlay, specialization file
without type file, same-named property collision} × repo {newly initialized,
existing with defaults absent, existing with user-edited schema of same name,
legacy flat layout} × entity population {existing entities revalidated — must stay
green} × enum use {both unified enums referenced from multiple schemata}.

### 7.3 Invariants

- **I-D1:** the template's ensure-missing pass never overwrites an existing file in
  any repo (`.arch-repo/schemata/` or elsewhere) — pre-existing guarantee, now
  regression-locked for the new files.
- **I-D2:** v1 guidance documents import and serve exactly as before (format bump
  is additive).
- **I-D3:** guidance composition is deterministic and additive — along the
  concept's ancestry path in the owning module's declared hierarchy, root-most
  first (archimate-4: domain → type → specialization); no level overrides another;
  absent levels are skipped silently; a document naming a level the module does
  not declare is a strict-import error, never a silent slot.
- **I-D4:** shipped schemata introduce no `required` attributes — startup schema
  validation over existing repos remains green with zero entity edits.
- **I-D5:** the Sensitivity and Lifecycle State enums are single-sourced in the
  defaults module and referenced by every schema that uses them (no drift between
  the three specialization schemata).

### 7.4 Failure modes with S|O|D

| ID | Failure mode | S | O | D | RPN | Primary mitigation |
|---|---|---|---|---|---|---|
| F4.1 | Template overwrites a user-edited schema file | 7 | 2 | 6 | 84 | I-D1 ensure-missing only; regression test writing a sentinel edit then re-running the ensure pass |
| F4.2 | Type/specialization schema resolved inconsistently across surfaces (validator vs GUI editor vs registry snapshot) | 4 | 4 | 5 | 80 | Extend the EXISTING `compute_effective_attribute_schema` (never a second resolver); verify all consumers delegate to it; unit matrix incl. same-named property |
| F4.8 | WU completion silently depends on the licensing-separated extract file absent from fresh sessions | 4 | 5 | 4 | 80 | Portable redacted fixtures for all tests; explicit owner checkpoint for the real-extract restructure/re-import |
| F4.9 | Diagram-type guidance implemented despite the OntologyModule-only scope | 5 | 8 | 4 | 160 | Contradictory examples removed from the plan; registry-kind test (dormant disabled OntologyModules, ignored DiagramTypeModules) |
| F4.10 | Independently chosen schema keys make model data, GUI, and docs disagree | 5 | 7 | 5 | 175 | §7.1b exact payload table; structural JSON assertions in WU-D2 |
| F4.3 | New defaults break startup validation of an existing repo | 5 | 3 | 3 | 45 | I-D4 nothing required; integration test: startup policy green on a fixture repo with pre-existing entities |
| F4.4 | v2 guidance file rejected or mis-parsed by strict import | 3 | 4 | 3 | 36 | Parser + import CLI unit matrix over §7.2 dimensions; v1 fixture regression |
| F4.5 | Ancestor-level guidance duplicated into every type response (bloating agent context) | 3 | 4 | 4 | 48 | Serving contract §7.6: ancestor levels appear once per response, keyed by level+node, not merged into each type's text; asserted in the serving unit test |
| F4.6 | MCP response-shape change breaks existing agent/skill consumers of `artifact_authoring_guidance` | 6 | 4 | 5 | 120 | §7.6 additive-only rule; v1-shape contract regression test pinned against a fixture |
| F4.7 | GUI guidance rendering crowds out or obscures the actual form (usability inversion) | 3 | 4 | 5 | 60 | §7.6 presentation rules (labeled, collapsible, once per view); Vitest presentation states |

### 7.5 User scenarios & stories

- **D-S1 (modeler/agent, guidance):** *Asking for strategy-domain authoring
  guidance returns the domain-level framing (business model, organization-independent,
  at-rest vs in-motion) once, plus each type's litmus lines* — instead of the same
  distinctions duplicated per type. Expected: `artifact_authoring_guidance
  filter=['strategy']` response carries the levels distinctly (F4.5).
- **D-S1b (author, GUI):** *Creating a strategy-domain entity in the GUI, I see
  "Strategy domain — modelling context" as a labeled, collapsible section above
  the type's own guidance — once, even with several strategy types in view.*
  Expected: §7.6 presentation rules hold; dismissing/collapsing persists for the
  session; the form itself stays the visual focus (F4.7).
- **D-S2 (owner, new repo):** *A freshly initialized engagement repo already has
  the business-object and Service/Module/Endpoint schemata; the existing
  ENG-ARCH-REPO gains the missing files on the next ensure pass without touching
  its six existing schema files.*
- **D-S3 (author, typed editing):** *Creating an application-component with
  specialization Service offers the seven Service attributes (typed: string lists,
  uri, Lifecycle State enum) merged over any type-level attributes; a plain
  application-component is unaffected.*

### 7.6 Serving & presentation contract (MCP + GUI) 🔴

Multi-level guidance is only worth shipping if it reaches humans and agents in a
maximally usable, intelligible form, implemented to the same architecture standard
as everything else. Binding rules:

- **One composition path.** Pure composition (ancestry resolution + assembly) lives
  in the domain layer; one application use case exposes it; the MCP tool
  (`artifact_authoring_guidance`), any GUI REST guidance route, and any other
  consumer are thin adapters over that use case. No second composition site, no
  adapter-local merging.
- **MCP response shape — additive, never breaking.** Agents and skills already
  consume `artifact_authoring_guidance`; every existing key (`entity_types` with
  `create_when`/`never_create_when`/`specializations`, `viewpoints`,
  `connection_types`, `total`, `domains`) keeps its name, type, and value shape
  (object order is not part of the contract; ordering is pinned only where
  semantically meaningful). v2
  adds one new top-level section — ancestry context keyed by `{level, node}` with
  human-readable level labels from the module declaration — ordered root-most
  first and deterministic. When several requested types share an ancestor, its
  context appears **once** in that section (types reference it implicitly by their
  domain/ancestry), never inlined per type (F4.5). A contract regression test pins
  the v1-shaped subset **structurally** (parsed-structure equality on keys, types,
  and values) — not byte-for-byte or by JSON key position, since object order is
  not the semantic API.
- **Intelligibility.** Each context block is labeled with its level and node in
  plain language ("Strategy domain — modelling context"), not raw keys; ordering
  always tells the reader "general framing first, then your type's litmus, then
  the specialization"; no block is ever truncated or summarized by the server.
- **GUI presentation.** WU-D1 first inventories the actual GUI guidance consumers
  (entity create/edit forms, connection forms, pickers — verified at the code, not
  assumed). Wherever type guidance is shown, ancestor context renders above it as
  clearly labeled, collapsible, read-only sections — shown once per view even when
  multiple types are on screen, collapsed by default when the user has seen the
  same node's context in the session (small, dismissable — guidance must help, not
  crowd out the form).
- **Engineering quality.** The global gates apply with no Part-D discount:
  hexagonal layering (domain composition pure and registry-driven; adapters thin;
  wiring only at composition roots), **validated branded strings** for level
  identity (registry-checked at parse/import — not compile-time closed unions,
  which module extensibility forbids; everywhere else closed unions still apply),
  typed DTOs at boundaries (no untyped values escaping adapters), LoC policy on
  every touched file, separate test file per component/use case, and the
  dependency-policy AST test must stay green.

### 7.7 Test strategy

| Level | Coverage |
|---|---|
| Domain/application unit | Guidance parser v1+v2 fixtures; composition order/determinism (I-D3); serving shape incl. shared-ancestor dedup (F4.5); v1-shape contract regression against a pinned fixture (F4.6); schema overlay resolution matrix (F4.2); enum single-sourcing (I-D5, an import-level assertion). |
| Backend integration | Import CLI strict/lenient over known/unknown keys at every level; template ensure pass on fixture repos (new, existing-with-defaults, user-edited sentinel — F4.1/I-D1); startup schema policy green with new defaults over pre-existing entities (F4.3/I-D4). |
| Frontend Vitest | Typed attribute editor renders the Service/Module/Endpoint sets incl. enum selects and list editors (on the existing typed-property foundation); plain component unaffected. Guidance presentation states: labeled/collapsible/once-per-view, collapse persistence, form stays focal (F4.7/D-S1b). |
| Dogfood | Restructured extract re-imported `--strict`; ENG-ARCH-REPO + enterprise repo gain the new schema files; spot-check an entity of each shape. |

## 8. Part E — Documentation & deterministic media (D18)

### 8.1 Scope

**E1 — Documentation content.** Update to the current product: README capability
summary and "See it" section (amending the "every screenshot is the system
describing itself" claim to distinguish self-model content from synthetic
confidential-data examples); navigation, tier facets, and workflow/status
controls; strategy & value modelling plus the four shipped strategy viewpoints;
assurance graph exploration and ontology-driven edge authoring; security-signal
refresh, metric meanings and units, the VEX workflow, classification semantics,
locked states, and persistence refusal; virtual viewpoint attributes and
ephemeral/stamped exports; guidance format v2 and the specialization schema
convention; CLI/MCP/reference pages including regenerated MCP tables;
configuration for the co-located signal backend plus the public-backend
deprecation/migration guidance (not normal configuration); installation and
operational prerequisites for the refresh tooling; the `motivation-coverage`
viewpoint page — including the exact §10.2 coverage semantics (applicable
population, denominator, pass/gap/N-A, branch completeness, shortcut-as-gap,
visibility limits, parameters) with a branched false-green regression example,
cross-referenced with `requirements-coverage-gaps` (§10); an **upgrade operator
guide** (target discovery, check vs commit, credentials, backup, quarantine,
partial completion, resume, Docker startup, report examples — from a synthetic
previous-release fixture, paths/secrets redacted); and a guided **self-model
showcase** walking strategy → architecture → assurance → security posture.

**E2 — Deterministic screenshots.** Regenerate the media suite; capture at least:
content-first navigation with tier facet + workflow cluster; strategy overview;
resource investment heat map; assurance neighborhood explorer; security-posture
viewpoint with legend; the motivation-coverage table with a visible gap row;
Architecture Backend detail with Service-specialization attributes AND the
read-only derived-metrics panel; the locked/unavailable metrics state; a
stamped export example.

### 8.2 Invariants

- **I-E1 (global, fail-closed):** the capture harness blocks ALL live
  `/api/assurance/**` traffic, fulfills only declared synthetic fixture routes,
  fails on any unexpected request, runs against a temp workspace/store, and
  asserts the production connector was never constructed. Harness provenance —
  not a text scan of pixels — is the primary proof of origin.
- **I-E2:** every screenshot containing security metrics or assurance content is
  produced from an explicitly synthetic TLP:WHITE fixture and shows a visible
  "Synthetic documentation data" marker; fixtures arrive by route interception or
  a dedicated seeded test connector — production code contains **no documentation
  bypass**.
- **I-E3:** every image is generated by a named deterministic media test using
  stable entity IDs (never "first result") and is listed in a **media provenance
  manifest** (test name, fixture ID/commit/seed, entity IDs, viewpoint ID +
  parameter snapshot where applicable, theme/viewport, capture-tool version,
  output path, digest);
  images contain no secrets, operational CVEs, real dependency versions, or
  TLP:AMBER/RED values (denylist text scan + manual/OCR review). Every Markdown
  reference to a generated image has meaningful alt text (alt text is a document
  property — tested on the documents).
- **I-E4:** README/docs/reference/screenshots describe the same, current
  navigation and feature set (truth audit at closure).

### 8.3 Failure modes with S|O|D

| ID | Failure mode | S | O | D | RPN | Primary mitigation |
|---|---|---|---|---|---|---|
| F5.1 | Live assurance content reaches a tracked screenshot (text scans cannot prove pixels) | 9 | 6 | 8 | 432 | Fail-closed harness: block all live `/api/assurance/**`, fulfill only declared fixture routes, fail on unexpected requests, temp workspace/store, assert production connector never constructed; media provenance manifest (test, fixture, entity IDs, viewport, path, digest); denylist text scan for known operational identifiers + manual/OCR review of rendered content |
| F5.2 | README/screenshots remain visibly inconsistent with the product | 5 | 9 | 6 | 270 | E1/E2 executed together; I-E4 truth audit in WU-X1 |
| F5.3 | Documentation bypass leaks into production code | 6 | 3 | 5 | 90 | Fixtures via route interception/test connector only; review + grep gate |
| F5.4 | Unstable capture (dynamic entity choice, model drift) breaks media regeneration | 4 | 6 | 4 | 96 | I-E3 stable IDs; deterministic fixtures; link + generated-reference checks |

### 8.4 Acceptance checks (Part E)

Every image from a named deterministic test with a manifest entry; the
fail-closed harness run is the primary origin proof (I-E1); current navigation
labels visible; stable IDs; alt-text document test green; denylist scan +
manual/OCR review clean; link checking and generated-reference checks green;
manual visual review at desktop and narrow widths.

## 9. Part F — Persisted-format upgrade coverage (D19, WU-U0)

### 9.1 Migration-impact table (first WU-U0 artifact; verified, then maintained)

| Surface | Old shape | New shape | Detection | Policy | Owning WU |
|---|---|---|---|---|---|
| Repository default schemata | files absent | new resource/business-object/specialization schemas | probe exact missing filenames | auto-add missing defaults only; user-owned same-named files preserved byte-for-byte and reported, never overwritten | A0/D2 + U0 |
| Guidance cache + sidecar | format 1 | canonical format 2 | parse document + sidecar versions | **one-line cache-header text patch + sidecar field update** (§9.2): only `guidance_format` changes in the document; sidecar gains cache-format/migration fields, retaining original source digest; NO ancestor context invented; report recommends re-import from the licensed source; unknown/newer/malformed/mismatched cache → blocking manual finding, no partial rewrite | D1 + U0 |
| Public security SQLite | legacy ingest/vulnerability tables | schema metadata + administrative quarantine ONLY | schema-version + content probes | **administrative-only migration (Q11):** TLP:WHITE legacy rows → quarantine in the public file; **any above-WHITE row = blocking preflight finding** (commit writes nothing to this target; report carries table/PK metadata only, never raw payload; manual instructions: secure import/quarantine into the co-located store, or explicit verified purge/retirement); permanently `no_active_run` — no refresh instruction exists for this backend; an absent public file is no target and is never initialized | C0 + U0 |
| Co-located SQLCipher signals | same legacy tables, encrypted | versioned run-owned schema | unlocked schema probe | transactional migration: quarantine legacy rows, then a NEW refresh establishes the first active run; commit requires the established credential/unlock path; a locked store is an **unresolved migration**, never "current" | C0 + U0 |
| Viewpoint declarations (`.arch-repo/viewpoints.yaml`, built-in catalogue) | no trace grammar | trace_patterns/enum-set parameters/structured columns (§10.7) | declaration/format-version probe | previous files load unchanged, no rewrite; new grammar requires the bumped contract version; the default dry-run names incompatible definitions; downgrade explicitly unsupported (older parsers fail clearly, never drop fields); one validator for built-in + authored | G1 + U0 |
| Configuration: `signals_backend=encrypted` alias; combinations losing write capability under §6.0(a); deprecated public metrics | old settings valid | explicit backend values + capability predicate | settings probe | encrypted→`sqlcipher-colocated` (SQLCipher store) or blocking owner choice; capability-loss = explicit finding, never silent; public-sqlite metric deprecation finding with co-located instructions; legacy public rows above TLP:WHITE = **blocking preflight finding with secure-import-or-verified-purge instructions (Q11 — never public quarantine)** | C0/C1 + U0 |
| Assurance edge/reference data | historically unrestricted/mixed | reconciled typed edge/reference policy (WU-B0) | B0 preflight (edges and arch refs separately) | auto-repair only where semantics are certain; otherwise blocking/manual/grandfather per the B0 decision; deterministic repairs become **registered data migrations** reusable by other installations (a one-time developer-store script is not product upgrade functionality) | B0 + U0 |

### 9.2 Operational upgrade architecture (executable contract)

**Target abstraction (new, distinct from repository surfaces):**

```text
UpgradeTarget
  kind: repository | deployment_settings | guidance_cache
      | signals_sqlite | assurance_sqlcipher
  stable_id · display_location · current_version
  credential_requirement · dependencies
```

**Deployment identity = one pure `DeploymentLayout` resolver** shared by
runtime bootstrap, Docker, MCP/CLI composition, and upgrade discovery, as a
**two-stage algorithm** (a precedence slogan is not an algorithm; document
selection and field resolution are different categories):

*Stage 1 — settings-document selection* (exact order, first hit wins):
(1) explicit `--settings PATH`; (2) `DEPLOYMENT_ROOT/settings.yaml` (where
`DEPLOYMENT_ROOT` is the `--deployment-root` value); (3) the
**NEW process-level environment variable `ARCH_SETTINGS_PATH`** — deliberately
distinct from the existing `ARCH_SETTINGS_FILE`, which is and remains a
**host-side Compose bind-mount SOURCE** (`.env.example`:
`ARCH_SETTINGS_FILE=./config/settings.server.yaml`; compose mounts it onto the
container's live `/app/config/settings.yaml`) and must never be interpreted as
an in-container path (the literal host value would resolve to the baked
`settings.server.yaml`, not the live mounted file). Docker's entrypoint sets
`ARCH_SETTINGS_PATH=/app/config/settings.yaml` explicitly (equivalently:
passes `--settings /app/config/settings.yaml`); runtime, CLI, and upgrade all
honor `ARCH_SETTINGS_PATH`; the host→container mapping is documented in the
configuration/Docker docs (E1); (4) the
source-tree `config/settings.yaml` compatibility default, which is
**read-only** — never a migration target (package/VCS-owned); selecting it
while operational migrations are pending yields a blocking "no operator-owned
deployment settings" finding with instructions to create one under the
deployment root. Operational targets require an explicit deployment identity
(stage-1 hit 1–3); `--workspace` alone never discovers them.

*Stage 2 — per-field resolution*, normative manifest/source table (the
resolver is transcribed from this table — no key, variable, default, or base
is invented at implementation time; the `deployment:` settings section is NEW,
introduced by this plan — current settings contain no path keys):

| Manifest field | Active predicate | Settings key | CLI | Env source (existing unless marked NEW) | Deployment-root default | Compat default | Rel. base | Target kind | Secrets |
|---|---|---|---|---|---|---|---|---|---|
| `settings_document` | always | — (self) | `--settings` | `ARCH_SETTINGS_PATH` (NEW process selector; `ARCH_SETTINGS_FILE` stays host-side bind source, never read by the process) | `DEPLOYMENT_ROOT/settings.yaml` | source-tree `config/settings.yaml` (read-only) | — | `deployment_settings` | path reportable |
| `workspace_root` | repositories selected | `deployment.workspace_root` | `--workspace` | — | `DEPLOYMENT_ROOT/workspace` | current CWD/init behavior | settings dir | `repository` (per repo) | path reportable |
| `assurance_db_path` | assurance configured | `deployment.assurance_db_path` | `--assurance-store` | `ARCH_ASSURANCE_DB_PATH` (existing) | `DEPLOYMENT_ROOT/.arch-assurance/store.db` | workspace-relative `.arch-assurance/store.db` | settings dir | `assurance_sqlcipher` | path reportable; key via `ARCH_ASSURANCE_MASTER_PASSWORD`, never reported |
| `signals_db_path` | `signals_backend=sqlite` | `deployment.signals_db_path` | `--signals-db` | `ARCH_SECURITY_SIGNALS_DB_PATH` (existing) | `DEPLOYMENT_ROOT/.arch-assurance/signals.db` | workspace-relative default | settings dir | `signals_sqlite` | path reportable |
| `guidance_cache_root` | always | `deployment.guidance_cache_root` | `--guidance-cache` | — (none today; none added) | `DEPLOYMENT_ROOT/guidance-cache` | `~/.config/arch-repo/guidance-cache/` | settings dir | `guidance_cache` | path reportable |
| `archive_identity` (local) | archive `standard|worm` | — **derived**: the assurance DB itself (co-located; never a second path) | — | — | derived | derived | — | inside `assurance_sqlcipher` | as assurance row |
| `archive_identity` (s3-worm) | archive `s3-worm` | identity: `deployment.archive.s3_bucket` + `deployment.archive.s3_prefix` | — | see cloud subtable | — | env-only (today's adapter) | n/a | preflight-checked, not migrated in v1 | bucket/prefix/region reportable; credentials never |
| `archive_identity` (azure-worm) | archive `azure-blob-worm` | identity: `deployment.archive.azure_storage_account` + `deployment.archive.azure_container` + `deployment.archive.azure_state_container` | — | see cloud subtable | — | env-only (today's adapter) | n/a | preflight-checked, not migrated in v1 | account/containers reportable; `ARCH_AZURE_STORAGE_KEY` never |

**Cloud-adapter subtable (exact; transcribed from the adapters — nothing
invented at implementation time):**

| Adapter field | Settings key | Env (existing) | Role |
|---|---|---|---|
| S3 bucket | `deployment.archive.s3_bucket` | `ARCH_S3_BUCKET` | **identity** |
| S3 prefix | `deployment.archive.s3_prefix` | `ARCH_S3_PREFIX` | **identity** (two namespaces in one bucket must not deduplicate) |
| S3 region | `deployment.archive.s3_region` | `ARCH_S3_REGION` | operational (reportable) |
| S3 KMS key | — | `ARCH_S3_KMS_KEY_ID` | operational; id reportable |
| S3 object-lock mode | — | `ARCH_S3_OBJECT_LOCK_MODE` | operational (preflight-verified) |
| S3 retention days | — | `ARCH_S3_RETENTION_DAYS` | operational (preflight-verified) |
| S3 credentials | — | standard AWS credential chain | never reported |
| Azure storage account | `deployment.archive.azure_storage_account` | `ARCH_AZURE_STORAGE_ACCOUNT` | **identity** |
| Azure archive container | `deployment.archive.azure_container` | `ARCH_AZURE_CONTAINER` | **identity** |
| Azure state container | `deployment.archive.azure_state_container` | `ARCH_AZURE_STATE_CONTAINER` | **identity** (mutable state participates in identity AND preflight — a shared state container across deployments is a conflict) |
| Azure immutability days | — | `ARCH_AZURE_IMMUTABILITY_DAYS` | operational (preflight-verified) |
| Azure key | — | `ARCH_AZURE_STORAGE_KEY` (optional; `DefaultAzureCredential` when absent) | never reported |

Canonical archive identity tuples: S3 = (bucket, prefix); Azure = (account,
archive container, state container). Settings keys override env; env is the
compatibility default (adapters are env-configured today). Preflight verifies
reachability + WORM/immutability configuration; dedup operates on the identity
tuple.

Conflict rules (exact): two **explicit** authoritative selectors for the same
field with different canonical values ⇒ error before any target is opened or
created; a lower-priority default never conflicts with an explicit value;
equal canonical values from multiple sources are accepted with all provenance
reported. Every resolved value carries a typed source enum. The manifest carries canonical
physical identity (symlinks resolved), logical kind, configured/active state,
source provenance, and the settings-target identity; runtime and Docker
**accept the manifest** rather than re-resolving. The operator-owned settings
file is a versioned, atomic text-file target (`deployment_settings`) — the
`signals_backend=encrypted` rewrite and capability-loss findings apply through
it, idempotently, unknown fields byte-preserved. Acceptance: table-driven
permutation test over every selector source and conflict; two workspaces under
one home never discover each other's stores absent an explicit shared
identity; Docker upgrade and runtime open byte-identical canonical paths from
one manifest; the source-tree settings file is never rewritten.

Each kind has a scanner/detector, ordered migration steps, a target-appropriate
writer/unit of work (databases get transactional migration connections — they
are NEVER forced through `RepoUpgradeWriter`, which stays repository-only), and
report details. Repository `ScannedSurface` remains the closed vocabulary for
repository content. **No cross-target atomicity is claimed**: the global
property is all-target discovery + preflight before any write, then ordered,
per-target atomic, idempotent, resumable application; a failure after an
earlier target committed produces an accurate partial report and a safe rerun.

**CLI discovery — deployment-scoped (normative):** `--workspace PATH` selects
**repository roots only** (unchanged semantics; a test workspace can never
reach the user's real global cache/stores). Operational targets bind to an
**explicit deployment identity**: `--deployment-root PATH` (or `--settings
PATH`) selects the configuration whose guidance-cache/store paths become
targets; `--guidance-cache PATH`, `--signals-db PATH`, `--assurance-store
PATH` override individually. Docker passes its exact settings/volume paths —
never a process user's global defaults. `--exclude-target KIND` is permitted
for operator-run partial commands (report then states deployment readiness is
NOT certified) and **forbidden during Docker startup readiness** (excluding a
configured active target while the software will immediately use it is a
contradiction). **CLI compatibility (additive evolution — a safe-unattended-upgrade tool
never breaks its contract):** every existing flag and behavior is preserved
and pinned in a compatibility table — `--repo-root`, `--workspace`,
`--commit`, `--json`, `--resolve-selection`; the live-backend serving guard;
repository transaction recovery and stale-temp sweep; dirty-overlap
informational behavior; the supported-floor/coverage disclaimer ("no known
issues", never "fully current"); per-repository detection semantics. **Default
invocation stays dry-run** (no `--check` flag; `--commit` is the only mutating
mode, gated on a clean all-target preflight). **Exit codes — normative state table (existing semantics preserved exactly;
compatibility means current scripts keep working, not merely "code 3 kept"):**

| Mode | State | Exit | Writes? | Report obligation |
|---|---|---|---|---|
| dry-run | clean | 0 | none | human + JSON, `repos` retained |
| dry-run | findings only (non-blocking) | 0 | none | findings in report — **compatibility: dry-run evaluation success is 0 regardless of findings** (current behavior; a future non-zero check mode would be a new opt-in flag) |
| dry-run | commit-blocking migration detected | 0 | none | blocking findings marked in report; Docker readiness reads the report state, not the code |
| dry-run | credential-uninspectable target | 0 | none | target reported `uninspectable`; deployment readiness NOT certified |
| commit | success | 0 | applied | full report |
| commit | repository-target internal step errors (existing narrower repository semantics, explicitly grandfathered as the ONE exception to per-target atomicity for repositories) | 1 | partial within that repository target | existing behavior preserved; report marks the repository target incomplete |
| commit | unresolved blocking migration | 3 | no migration writes (separately reported pre-existing consistency repair may have written) | `EXIT_UNRESOLVED_MIGRATION` — existing constant + regression test |
| commit | ≥1 complete `UpgradeTarget` unit committed, then a LATER target failed | 20 | committed targets only | `EXIT_PARTIAL_APPLY`; exact partial report + resume instructions. Precedence: 20 wins over 1 when both apply (cross-target failure dominates within-repository step errors) |
| commit | infrastructure/credential failure before any target commit | 21 | no migration writes (pre-existing consistency repair may have written, separately reported) | `EXIT_INFRASTRUCTURE_FAILURE` |

stdout = human report (or JSON with `--json`); stderr = diagnostics; Docker
startup maps EVERY code to a documented readiness outcome (0 → proceed;
1/3/20/21 → halt with the report reason); table-driven tests cover the three
distinct failure locations (repository-internal error → 1, later-target
failure → 20, pre-apply infrastructure failure → 21) and reports distinguish
recovery/cleanup writes from migration writes; orchestration maps named report
states, never bare numbers. **Phase order (honest about
recovery writes):** (1) target discovery + physical dedup; (2) read-only
credential/path/backend-serving readiness; (3) repository recovery *plan*;
(4) explicitly classified pre-existing consistency repair (repository
transaction recovery/stale-temp sweep — an existing behavior, reported as
such; the "no writes before preflight" guarantee applies to *migration*
writes, and this is stated, not hidden); (5) re-scan + all-target semantic
preflight; (6) ordered per-target apply. Target identity = canonical storage
location + kind with physical deduplication (symlinks resolve; co-located
signal tables migrate INSIDE the single `assurance_sqlcipher` target
transaction — one physical database opens once). JSON report additively
compatible: `report_schema_version` added; existing `repos` key retained
structurally; new `operational_targets` and `deployment_preflight` sections;
coverage disclaimer present in human + JSON forms.
Credentials come only through the established non-interactive secret path; an
existing locked SQLCipher store whose version cannot be read is a **blocking
unresolved migration** (never "current"); reports and logs never contain
secrets. Backup policy and operator recovery steps are stated per target kind.

**Docker startup (reordered, normative):** (1) resolve configuration + target
locations without opening stores; (2) obtain credentials non-interactively;
(3) discover + preflight every existing target; (4) apply ordered migrations;
(5) verify versions; (6) initialize absent optional stores at current version
(not a migration); (7) only then start ordinary connectors/services. Ordinary
store constructors must NOT auto-create current tables before the detector has
read the prior schema.

**Guidance cache v1→v2 (exact transformation):** canonical v2 preserves the v1
`entity_types`/`connection_types` leaf slots, so the migration is a
**version/header + sidecar transformation applied as a TEXT PATCH** — a YAML
parse/reserialize cannot promise comments, scalar style, ordering, or bytes,
so the document change is exactly one line (`guidance_format: 1` →
`guidance_format: 2`) with every other byte preserved. Sidecar fixture
(complete key set, normative): existing `source`, `sha256` (continues to refer
to the ORIGINAL source file, not the transformed cache), `guidance_format`,
`imported_at`, match counts, unmatched keys — plus new `cache_format_version:
2`, `migration_step` (id/version), `migrated_at` (UTC ISO-8601),
`original_format: 1`. NO ancestor context invented; unknown fields preserved
verbatim; cache keys unchanged; report: "compatible, migrated header;
domain-level enrichment requires re-import from the licensed source".
Synthetic before/after fixtures (full file + sidecar) prove the transformation
ahead of the licensed-extract owner checkpoint; malformed/newer/mismatched
caches are blocking manual findings with no partial rewrite.

**Legacy signal quarantine (exact DDL, normative):**

```sql
CREATE TABLE legacy_signal_quarantine (
  quarantine_id INTEGER PRIMARY KEY,
  source_table TEXT NOT NULL,
  original_pk TEXT NOT NULL,          -- canonical JSON array of PK values
  raw_payload TEXT NOT NULL,          -- canonical JSON object: column → typed value
                                      -- {"t":"null|int|real|text|blob","v":...};
                                      -- blob = base64
  reason_code TEXT NOT NULL,          -- closed: no_run_identity | global_vex |
                                      -- unparseable | above_public_ceiling |
                                      -- duplicate_identity | unknown_schema
  source_schema_version INTEGER NOT NULL,
  migrated_at TEXT NOT NULL,          -- UTC ISO-8601
  UNIQUE (source_table, original_pk)  -- rerun safety: re-quarantine is a no-op
);
```

Written in the same per-target migration transaction; counts in the upgrade
report; queryable via `arch-repair quarantine list|show` (admin surface;
payload values redacted per classification; available for the public SQLite
file — where it may reveal TLP:WHITE payloads only, behind the same local
operator access as the CLI itself, since above-WHITE content never enters that
file); no partial row
conversion; backup expectation stated before commit; **co-located metrics remain
`no_active_run` until a clean refresh creates an active current-format run;
public-file metrics are permanently `no_active_run` in v1 (no refresh path
exists — Q10/Q11)**.
SQLCipher migrations use an explicit credential-bearing raw migration
connection and one target transaction; ordinary constructors never auto-create
ahead of detection.

**Migration mechanics appendix (normative — the executor implements, never
designs):**
- Schema metadata: public SQLite gets `signal_schema_meta(key TEXT PRIMARY
  KEY, value TEXT)` with key `signal_schema_version`; inside the co-located
  SQLCipher store the SAME table name holds the signal-table version —
  deliberately distinct from the assurance store's own schema-version key, so
  the two version spaces never collide. Legacy stores without the table are
  version 0.
- Versions/steps: legacy = 0, run-owned schema = 1; step id
  `signals-0001-run-aggregate` (detector: version < 1; both physical layouts);
  future steps append ordered ids with explicit dependencies.
- Quarantine reason precedence (first match wins): `unknown_schema >
  unparseable > above_public_ceiling > global_vex > no_run_identity >
  duplicate_identity`. In the **co-located store**, ALL legacy signal rows are
  quarantined (semantics are never provably complete for run-less rows). In the
  **public file**, only TLP:WHITE rows quarantine there;
  `above_public_ceiling` rows never land in the public quarantine — they are a
  blocking preflight finding (Q11; moving confidential data between tables of
  the same plain file is not protection). TLP never promotes a row into a
  current run.
- `original_pk`: canonical JSON array of the table's declared PK values in
  column order; tables without a declared PK use `["rowid", <rowid>]`;
  composite keys serialize all members; a table where neither exists is a
  blocking finding.
- `raw_payload` canonical JSON — EVERY column value is a typed wrapper object
  (uniform; no bare values), UTF-8, keys in table column order, separators
  `", "`/`": "` per json.dumps defaults, standard base64 alphabet WITH
  padding; SQLite has no boolean (integers stay `int`); timestamps are
  whatever the column stored (text/int/real — no reinterpretation). Canonical
  example (normative fixture):

  ```json
  {"column_a": {"t": "text", "v": "value"},
   "column_b": {"t": "int", "v": 42},
   "column_c": {"t": "real", "v": "nan"},
   "column_d": {"t": "blob", "v": "AAE="},
   "column_e": {"t": "null"}}
  ```

  Finite reals are JSON numbers in `v`; non-finite reals are the strings
  `"nan"|"inf"|"-inf"`; text with invalid UTF-8 falls back to
  `{"t":"blob"}`. Round-trip reconstruction tests (not just string
  snapshots) cover every SQLite storage class.
- Settings rewrite (`deployment_settings` target): atomic
  write-temp-then-rename; **supported forms are declared** — a plain
  block-mapping scalar (`signals_backend: encrypted`, optionally quoted,
  optional inline comment): the patch is a token/span-aware scalar replacement
  changing only that token and preserving every other byte incl. the comment
  and line ending (CRLF preserved as found); flow-style mappings, duplicate
  `signals_backend` keys, and anchors/aliases on that key are **blocking
  manual findings** with exact instructions; idempotent (second run = byte
  no-op). Fixtures: quoted, unquoted, inline-comment, CRLF, malformed,
  duplicate-key, and flow-style each with a defined migrate-or-block result.
Fixtures: empty, valid-legacy, corrupt, unknown-schema, global-VEX,
above-ceiling, duplicate, no-PK, composite-PK, BLOB, and already-quarantined
stores; first run deterministic counts/reasons, second run no-op; no legacy
row in current metrics; both layouts expose an unambiguous version.

**Work split:** **WU-U0a** (target/report/CLI/startup foundation) precedes
every persisted-format change; each surface's detector/migrator co-lands with
its format change (C0 stores, D1 cache, G1 viewpoint grammar, A0/D2 schemata);
**WU-U0b** (previous-release fixtures, partial-failure/resume, Docker
integration) closes the stream.

### 9.3 Failure modes with S|O|D

| ID | Failure mode | S | O | D | RPN | Primary mitigation |
|---|---|---|---|---|---|---|
| F6.1 | Older repo/cache/signal store reports "current" or loses legacy data because no registered migration covers a new format | 9 | 6 | 7 | 378 | §9.1 inventory + registered versioned steps + previous-release fixtures (two-level negative tests) |
| F6.2 | Legacy vulnerability rows given fabricated run/anchor/applicability semantics during migration | 8 | 4 | 7 | 224 | Quarantine policy (§9.1); migration never synthesizes semantics; fixture test |
| F6.3 | Cache migration invents ancestor context or loses provenance | 6 | 4 | 6 | 144 | Header text-patch-only migration + sidecar provenance + "re-import recommended" report; before/after byte fixture test |
| F6.4 | Dry-run writes, or a blocking finding fails to gate `--commit` | 8 | 3 | 6 | 144 | Existing framework contracts extended to new targets; purity + gate tests |
| F6.5 | Docker starts against a previous operational-store schema it cannot discover/unlock/upgrade | 9 | 7 | 6 | 378 | §9.2 startup reorder + non-interactive credentials + previous-release volume fixture |
| F6.6 | Cross-target apply partially completes and cannot safely resume | 8 | 5 | 6 | 240 | Per-target transactions + dependency order + partial report + resume test |
| F6.7 | New viewpoint grammar saved without declared format impact (downgrade silently drops fields) | 7 | 7 | 7 | 343 | §9.1 viewpoint row + contract-version fixtures; older parsers fail clearly |
| F6.8 | Upgrade discovers/mutates another deployment's cache or stores, or skips one Docker will open | 10 | 7 | 7 | 490 | §9.2 DeploymentLayout resolver shared with runtime; deployment_settings target; two-workspace isolation + Docker same-manifest tests |
| F6.9 | Exit-code/flag reassignment breaks existing automation (EXIT_UNRESOLVED_MIGRATION=3) | 8 | 7 | 7 | 392 | §9.2 additive CLI table; code 3 preserved + regression; new codes 20/21 |
| F6.10 | Failed-run replay ambiguity (resume vs return) corrupts operator expectations | 6 | 6 | 7 | 252 | §6.0(c) transition table: replay returns stored outcome; per-anchor key + full bundle digest; mismatch = typed no-write conflict |
| F6.11 | Above-WHITE legacy rows normalized into the plain public file, or an operator waits for impossible public metrics | 9 | 6 | 8 | 432 | Q11 split policy: blocking finding for above-WHITE; public file permanently no_active_run; docs never instruct a public refresh |
| F6.12 | Upgrade and runtime resolve different physical stores (settings/env/CLI category confusion) | 9 | 6 | 7 | 378 | §9.2 two-stage resolver; typed source enums; read-only source-tree settings; permutation + manifest-handoff tests |
| F6.13 | Dry-run exit-code reinterpretation breaks existing automation | 8 | 6 | 6 | 288 | §9.2 state→exit table: dry-run always 0; report carries state; existing fixtures pass unchanged |
| F6.14 | Quarantine/settings codecs invented divergently (rerun inequality, byte-preservation failure) | 7 | 5 | 7 | 245 | §9.2 canonical typed-wrapper JSON fixture + declared settings scalar forms; round-trip reconstruction tests |

### 9.4 Self-model delta (Part F)

| Element | Type | Change |
|---|---|---|
| Repository Upgrade Framework (`APP@1783872532.OZbaBh`) | application-component (existing) | Description/behavior updated: multi-target operational upgrade orchestration (repositories, guidance cache, both signal stores) with per-target transactions and resumable ordered application — explicitly NOT a distributed transaction. |
| Repository Format Upgrade | requirement (existing) | Broadened: covers repository AND operational persisted surfaces (cache, stores, viewpoint declaration grammar). |
| Upgrade Report | data-object (existing) | Extended semantics: target kind, versions, preflight, partial-apply, resume. |
| Guidance Cache | data-object (NEW) | The deployed, deployment-level guidance cache (`~/.config/arch-repo/guidance-cache/`) — materially distinct from DOB `Guidance Import Source` (the licensed source): different location, lifecycle, and upgrade target. Accessed (read/write) by `Load Guidance Content` and the upgrade framework. |
| New connections (exact witnesses) | — | `Repository Upgrade Framework (APP@1783872532.OZbaBh) —archimate-access→ Guidance Cache`; `—archimate-access→ Security Signals Store (DOB@1780656431.p04R7k)`; `—archimate-access→ Assurance Knowledge Base (DOB@1780656431.ApaPcg)`; `—archimate-access→ Upgrade Report (existing DOB)`; **`APP@1783872532.OZbaBh —archimate-realization→ Repository Format Upgrade (REQ@1783872530.VyosDa)`** — the component realizes the requirement directly; no new behavior entity (resource-optimal; revisit only if upgrade behavior becomes significant elsewhere). Acceptance verifies every witness by exact source ID, target ID, type, and direction; `artifact_verify` clean after the batch. |
| Naming | — | `Repository Upgrade Framework` / `Repository Format Upgrade` keep their names with descriptions explicitly stating scope = repositories AND deployment-level persisted surfaces (rename deferred — a rename cascades into docs/ADRs for no v1 gain; recorded as a conscious naming debt). |

## 10. Part G — Motivation coverage viewpoint (D20)

### 10.1 Verified mechanism baseline (third-pass corrected)

- Table presentation exists (`representation: table`, columns accept **only
  `label` + `source` (entity field)**, `group_by`, sortable rows, badge rules).
- Boolean parameters render as checkboxes, **but the parameter prompt opens only
  when a required parameter lacks a default** — a fully defaulted declaration
  executes with no visible controls; parameter binding resolves values as
  **operands in conditions only** (no guarding/switching of criteria,
  populations, alternatives, or filters); `max_query_parameters` defaults to
  **4** and authoring validation rejects more.
- Viewpoint table results are **executed projections**; saved viewpoint
  applications exist for diagrams/matrices only — a table result is not a
  persisted artifact and this part does not make it one.
- Cost baseline: `requirements-coverage-gaps` over 62 requirement rows took
  ≈3.7 s in the reviewed environment; the coverage view spans ≈85 rows ×
  multiple patterns — budgets are mandatory, not advisory.

### 10.2 Semantics — branch-complete full realization (owner decision, Q8)

The view reports **full realization** (existential reachability would
under-report exactly the gaps it exists to surface — the live model's assurance
goal has two outcome branches fanning out to two and three requirements, plus a
direct `archimate-influence` from REQ `Assurance as a Separate Module Family`).

**(a) Two distinct operations — never mixed:**
- **Branch enumeration uses DIRECT STORED edges only** (derived relationships
  would collapse, duplicate, or bypass modeled branches and defeat universal
  quantification): goal → its realizing outcomes = reverse of stored
  `archimate-realization` (outcome→goal); outcome → its realizing requirements
  = reverse of stored `archimate-realization` (requirement→outcome); direct
  requirement shortcut per (b).
- **Leaf coverage is existential over direct + derived realization chains**:
  from each terminal requirement obligation, incoming `archimate-realization`
  (direct, or derived composition per the existing rules, hop cap 4) must reach
  ≥1 element of the column's layer (module-declared domain+class membership).

**(b) Shortcut decision (Q9, option 1 — smallest safe):** a direct stored
`requirement —archimate-influence→ goal` (or `→ outcome`) connection counts as
a **shortcut branch** (status `shortcut`, verdict `gap`). Generic
`archimate-association` is NOT treated as realization intent — it yields the
diagnostic status `ambiguous_link` (verdict `gap`) listing the association, so
modelers see it without the view asserting realization. The live
`Assurance as a Separate Module Family —influence→ GOL Provide First-Class
Assurance…` link is the named acceptance witness for shortcut detection.

**(c) Branch identity = canonical TAGGED obligation tuples** — including
obligations for branches whose expected next node is absent (a denominator
containing only existing nodes cannot measure missing nodes):

```text
("requirement", root_goal_id, outcome_id, requirement_id)   # terminal
("requirement", root_outcome_id, requirement_id)
("shortcut",    root_goal_id, requirement_id)               # influence shortcut
("missing-requirement", root_goal_id, outcome_id)           # outcome w/o active requirement
("missing-outcome",     root_goal_id)                       # goal w/o any outcome or shortcut
```

Duplicate traversal paths to the same tuple collapse; distinct tuples never
collapse — a requirement realizing two outcomes is two obligations even when
one leaf realizer satisfies both. Reported per row: terminal
`covered/applicable` ratio (over "requirement"/"shortcut" tuples),
`incomplete_branch_count` (the missing-* tuples), and bounded failing/
incomplete tuple IDs. **A row is a gap whenever `incomplete_branch_count > 0`
or any terminal obligation is uncovered.** The mixed case — Goal with Outcome A
→ requirement → realizer AND Outcome B with no requirement — is therefore a
gap via `("missing-requirement", goal, outcomeB)`. Zero expected branches =
`("missing-outcome", goal)` = gap, never vacuous truth. Cycles over stored
branch edges terminate by visited-tuple set and yield status `cycle` (gap) on
that branch.

**(c2) Verdict composition (F1 — one authoritative verdict, layers are
diagnostics):** the row's authoritative verdict (what `gaps_only` filters and
row rank sorts) is composed from exactly TWO patterns: `motivation` branch
completeness AND `overall_realization` — a terminal obligation is covered when
≥1 eligible incoming direct/derived realization chain reaches ANY
ontology-permitted realizer type (the eligible set is **registry-derived** from
the requirement type's permitted incoming-realization sources at load — all
families: common behavior, business, application, technology, physical,
strategy, implementation/migration — minus motivation-only refiners and
junction/grouping helpers). The behavior/business/application layer columns are
**diagnostics**: their absence status is `none_observed` (verdict-neutral),
never a gap — no invariant requires realization in every layer, and the live
model legitimately contains application-only, business-object-only, and
technology-realized requirements. A bounded `realizer_layers` field lists the
layers where realizers were observed (incl. layers outside the three showcase
columns). The requirement-row `overall_realization` verdict agrees with the
shipped `requirements-coverage-gaps` "has an incoming realization" definition;
documented differences are only branch completeness and status policy.

**(d) Status registry (closed, stable codes with fixed precedence):**
`ok` (pass) · `shortcut` (gap) · `incomplete_branch` (gap; missing-* obligation
present) · `partial_branches` (gap; some terminal obligations uncovered) ·
`no_trace` (gap) · `ambiguous_link` (gap) · `cycle` (gap) · `observed` / `none_observed`
(diagnostic observations only — never verdicts) · `not_applicable`.
Precedence when several apply to one row/cell: cycle > ambiguous_link >
incomplete_branch > shortcut > partial_branches > no_trace > ok.

**(e) Scope policies:** rows = active + draft entities (draft participates —
REQ-C3 must appear); `deprecated`/`retired` entities are excluded as rows AND
as branches (an obligation realized only by a retired requirement is a gap,
listed with a diagnostic). `group` filters the **row population only**; branch
enumeration and leaf coverage always run over the full effective graph.
Combined engagement + enterprise scope is the effective graph (same-short-id
entities merge per the canonical identity rules); rows carry their tier
provenance; a nonexistent `group` value yields a typed empty result, not an
error.

### 10.3 Parameter & control contract (executable against the real mechanism)

**(a) `enum-set` parameter type (new persisted grammar — current parameters are
scalar-only, so this is specified exactly):**

```yaml
parameters:
  - name: scope
    type: enum-set
    allowed_values: [goal, outcome, requirement]   # order = canonical order
    min_items: 1
    default: [goal, outcome, requirement]
```

Runtime value: ordered, duplicate-free tuple normalized to declaration order.
Wire forms — REST JSON: array of strings; URL: repeated ordered query keys
(`scope=goal&scope=requirement`; one canonical form, not router defaults);
CSV/export provenance: dedicated `param:<name>` columns with the canonical
serialized value. Typed load/bind errors: empty set, unknown member, scalar
where array expected, > allowed cardinality. Frontend types are hand-declared
DTOs (D14: `types.generated.ts` untouched). Duplicates and reorderings
canonicalize identically (round-trip tested). Other parameters: `gaps_only`
(boolean, default false), `group` (slug, optional). 3 parameters — under the
cap of 4, which stays.

**(b) Execution pipeline (normative order — `gaps_only` and gaps-first sorting
consume verdicts, so filtering/sorting is a POST-projection phase, a genuine
mechanism addition):**

```text
parse + validate declaration
→ bind + canonicalize parameters
→ pre-query row-population conditions (scope via a set-valued binding in the
  EXISTING `in` condition on entity type; group filter)
→ materialize the COMPLETE retained row population within the request budget
→ evaluate all applicable trace patterns (memoized, one adjacency snapshot)
→ compute per-row worst-verdict rank
→ post-projection filter (gaps_only ⇒ verdict = gap; N/A-only rows excluded)
→ global deterministic sort (worst verdict, then type, then name)
→ response/page limit
→ project ONE DTO to REST/GUI/CSV
```

There is **no generic `when:` guard grammar** — the earlier proposal is
withdrawn as bloat: `scope` binds into the existing `in` condition, and
`gaps_only` is a post-projection filter; nothing else needed conditional
activation (and parameter-only guards could never cycle, making the planned
cycle validation vacuous). Budget abort at ANY stage returns a typed error and
no authoritative partial table. A gap beyond any legacy pre-trace limit still
appears under `gaps_only` (the population materializes before limiting —
acceptance-tested).

**(c) Controls:** execution surfaces render an always-available parameter
toolbar even when every value is defaulted (mechanism-level extension of the
prompt-only-if-required behavior); changing a parameter re-executes and updates
the URL query via `router.replace`; a copied URL reproduces the exact canonical
parameter snapshot and result.

### 10.4 Trace patterns, verdicts, and projection DTO

**Result DTO (one contract for GUI, REST, CSV) — a discriminated union, since
diagnostic absence is neither pass, gap, nor not-applicable:**

```text
PatternResult =
  AuthoritativePatternResult {
    role: authoritative,
    verdict: pass | gap | not_applicable,
    status_code: <§10.2d registry>,
    coverage: {covered, applicable},        # terminal obligations
    incomplete_branch_count,
    failing_obligations: [tagged tuples, cap 5 + overflow count],
    last_satisfied_ids: [stable ids, cap 5],
    missing_expected: [declared type descriptors],
    shortcut: bool,
    diagnostic_code?: cycle | budget_aborted | ambiguous_link }
| DiagnosticPatternResult {
    role: diagnostic,
    observation: observed | none_observed | not_applicable,
    status_code: observed | none_observed | not_applicable,
    last_satisfied_ids: [stable ids, cap 5] }
```

The **row-level verdict** remains `pass | gap | not_applicable`, composed from
exactly `motivation` + `overall_realization`; sorting and `gaps_only` read only
that row value — never diagnostic observations. `realizer_layers`: cap 8,
deterministic (declaration order then name), overflow count. CSV columns per
role: `trace:<authoritative>:verdict|status|coverage|missing|witness_ids`;
`trace:<diagnostic>:observation|status|witness_ids`; plus `param:<name>`
provenance columns — never `str(value)`. GUI cells always carry textual
status/observation. Diagnostic absence never serializes as authoritative
`pass`, `gap`, or a false `not_applicable` (fixture-tested: an application-only
requirement passes overall while its business diagnostic reads
`none_observed` identically in GUI, REST, CSV, and authoring preview).

**Formal grammar (one canonical schema — YAML, domain value objects, REST and
GUI authoring DTOs, validator, and migration detector all implement exactly
this; TASKS contains no construct absent from it):** a trace pattern is the
closed kind `branch-complete-realization` with tagged node variants. Branch
quantification (universal over branches, existential at the leaf) is **fixed
mechanism behavior of this kind**, not authorable grammar — there are no
steps/alternatives/quantifier keywords. Named reuse is by **immutable value
expansion at load**, same-document scope only, acyclic (validated), serialized
preserving the reference:

```yaml
trace_patterns:
  - name: motivation
    kind: branch-complete-realization
    applies_to: [goal, outcome]
    branches:                                # tagged: kind stored-edge
      goal_to_outcome:
        {kind: stored-edge, connection: archimate-realization,
         direction: incoming, endpoint: {type: outcome}}
      outcome_to_requirement:
        {kind: stored-edge, connection: archimate-realization,
         direction: incoming, endpoint: {type: requirement}}
    shortcuts:                               # tagged: kind diagnostic-edge
      - {kind: diagnostic-edge, connection: archimate-influence,
         direction: incoming, endpoint: {type: requirement}, status: shortcut}
      - {kind: diagnostic-edge, connection: archimate-association,
         direction: incoming, endpoint: {type: requirement},
         status: ambiguous_link}
    leaf: {kind: none}                       # branch completeness only
  - name: overall_realization               # THE authoritative realization verdict
    kind: branch-complete-realization
    applies_to: [goal, outcome, requirement]
    branches: {ref: motivation}              # immutable value expansion of branch edges only
    leaf:
      kind: derived-reachability
      connection: archimate-realization
      traversal: direct_and_derived
      max_hops: 4
      endpoint: {registry: permitted-realizers-of-requirement}
      # registry-derived eligible set; excludes motivation refiners + junctions/groupings
  - name: behavior_coverage                  # DIAGNOSTIC column (none_observed, never gap)
    kind: branch-complete-realization
    applies_to: [goal, outcome, requirement]
    branches: {ref: motivation}
    diagnostic: true
    leaf: {kind: derived-reachability, connection: archimate-realization,
           traversal: direct_and_derived, max_hops: 4,
           endpoint: {domain: common, class: behavior-element}}
  - name: business_coverage
    kind: branch-complete-realization
    applies_to: [goal, outcome, requirement]
    branches: {ref: motivation}
    diagnostic: true
    leaf: {kind: derived-reachability, connection: archimate-realization,
           traversal: direct_and_derived, max_hops: 4, endpoint: {domain: business}}
  - name: application_coverage
    kind: branch-complete-realization
    applies_to: [goal, outcome, requirement]
    branches: {ref: motivation}
    diagnostic: true
    leaf: {kind: derived-reachability, connection: archimate-realization,
           traversal: direct_and_derived, max_hops: 4, endpoint: {domain: application}}
```

Grammar contract: closed tagged unions (`stored-edge | diagnostic-edge` for
edges; `none | derived-reachability` for leaves; `mapping | {ref: name}` for
branches — discriminated by shape, validated); `{ref: X}` expands X's
`branches` value only (never shortcuts/leaf/status semantics); `diagnostic:
true` marks a pattern verdict-neutral (`none_observed` on absence); requirement
rows have the single obligation `("requirement", root_requirement_id)` and
`motivation` is `not_applicable` for them; defaults, structural caps (≤ 8
patterns, ≤ 8 edge declarations, ≤ 4 hops), format version, deterministic
serialization, and typed error codes are part of the schema. Round-trip
acceptance: one **machine-readable schema** enumerates every accepted field
and tagged variant; a schema-derived positive/negative fixture corpus is
shared by loader, authoring GUI, REST, and the upgrade detector; YAML → domain
→ YAML structural identity; REST and GUI DTOs → same domain object; caps
tested at limit and limit+1; unknown variants/fields and cyclic refs fail at
load; searching the active contracts for the deleted step/alternative/status-
rule vocabulary returns no normative occurrence.

### 10.5 Budgets (load-time structural + one request-wide)

Load-time caps (validated, over actual §10.4 schema fields only): ≤ 8 trace
patterns/viewpoint; ≤ 8 stored + diagnostic edge declarations per pattern
**measured after `{ref}` expansion** (bounds actual work); `{ref}` expansion
depth ≤ 2 and ≤ 4 named references per declaration; derived-leaf `max_hops`
≤ 4. Model branch fan-out is runtime expansion, accounted solely against the
request-wide budget — it is not a declaration property.
Execution: one request-wide evaluation budget (default expanded-node count
frozen ONLY after a WU-G1 sizing spike — the spike defines the expansion
accounting unit (one traversal expansion of one obligation/leaf step),
measures the ≈85-row live model and a deterministic 5× branching fixture cold
and warm, and derives the default + hard clamp from measurements; plus the
existing request time budget) **bound to the same budget object and failure
semantics as viewpoint execution generally**; one filtered adjacency snapshot
per execution; memoization keyed ONLY by trace inputs — model/read snapshot
revision, effective repo/tier scope, entity, declaration digest, pattern/edge
declaration, direction, endpoint constraints, and applicable visibility
context. **No assurance/security state in the key** (`SignalSnapshotToken`
belongs exclusively to the signal-derived attribute capability; a future
external-source pattern would carry its own explicit provider snapshot):
lock/unlock or signal-run activation never invalidates a pure motivation
trace; model revision does (a dependency-policy test proves the trace domain
imports no assurance/security connector or lock type).
Budget exhaustion aborts the execution with a typed error — it never converts
unknown work into a pass or gap and never returns a mixture of authoritative
and missing cells. Performance acceptance (objective, repeatable protocol): deterministic
fixture seed; cold-process runs plus a stated warmup count; ≥ 30 samples for
p95; machine/runtime metadata and the configured timeout value recorded with
the evidence; p95 of the live-model execution and the 5× fixture ≤ **70% of
the configured request timeout**; the budget default must NOT abort ordinary
live-model execution; model-outgrows-default behavior = typed abort with
configured-clamp guidance; repeated protocol executions produce comparable
evidence records.

### 10.6 Executed table, not a saved diagram

The persisted artifact is the **catalogue/repository definition**, never the
result: acceptance = definition save/load round-trip; two executions around a
model change proving re-evaluation; repository scan proving no computed cells
or witness paths persist; a shareable URL (viewpoint ID + parameter snapshot).
A persisted "table application" or a gap *diagram* are separately scoped future
features (§14).

### 10.7 Persisted-format impact (feeds Part F)

The declaration grammar (`trace_patterns`, `applies_to`, the §10.4 tagged
edge/leaf/ref variants, enum-set parameters, structured column kind) is **itself a persisted-format change**: repository-
authored definitions live in `.arch-repo/viewpoints.yaml`. Contract: previous
declarations load unchanged (no rewrite); newly saved trace declarations
require the bumped `FORMAT_CONTRACT_VERSION`; the default dry-run invocation
detects unsupported/malformed declaration versions and names the responsible
repository/definition; downgrade to older software is explicitly unsupported
(older parsers must fail clearly, not drop fields); built-in catalogue and
repository-authored definitions share one validator. Row added to §9.1.

### 10.8 Self-model delta

| Element | Type | Rationale & relations |
|---|---|---|
| Evaluate Trace Coverage Columns | function (new) | Branch-complete pattern evaluation producing row projection DTOs (discriminated PatternResult union) during viewpoint execution. Realizes REQ-G1 + REQ-G2; assigned to APP `Query Binding Evaluator`; served by APP `Relationship Derivation Engine`; accesses DOB `Canonical Per-Repo Artifact Index`. |
| Trace Coverage Projection | data-object (new) | The transient executed projection (rows + discriminated PatternResults) served to GUI/REST/CSV — never persisted (I-G1). |
| Motivation Coverage Reporting | requirement (new, REQ-G1) | Realizes OUT `Requirements Traceable to Realized Components` (`OUT@1776629105.9jS0BB`); supports CAP `Architecture Analysis & Visualization`. |
| Computed Viewpoint Table Columns | requirement (new, REQ-G2) | The generic mechanism (enum-set parameters, post-projection pipeline, structured columns, row projection DTO, budgets). Association → REQ `Viewpoint-Based Model Presentation`; realized by the new function. |
| Viewpoint Definition | business-object (existing) | Description extended: trace patterns, enum-set parameters, structured columns; format-version note. |

### 10.9 Dimensions & variations

Row type × scope subsets × branch shapes {zero-branch, one-of-two complete
(false-green regression), convergent duplicate paths, cyclic subgraph,
shortcut-only, multi-realizer leaf, budget-aborted branch} × applicability
{in/out of `applies_to`} × parameters {scope subsets incl. rejected-empty,
gaps_only, group set/unset/nonexistent} × visibility {hidden branch entity} ×
presentation {GUI, REST, CSV, copied URL} × definition source {built-in
catalogue, repository-authored, previous-release file without trace fields}.

### 10.10 Invariants

- **I-G1:** computed cells/witnesses are never persisted (definition round-trip
  + re-execution + repository scan prove it).
- **I-G2:** verdicts are pure, deterministic functions of (model snapshot,
  declaration, parameter snapshot) — independent of database row order.
- **I-G3:** verdict partition {pass, gap, not_applicable} is total; `gaps_only`
  retains exactly `verdict = gap`; zero-expected-branch cases are gaps; the
  coverage ratio's denominator counts stable entity identities once.
- **I-G4:** layer membership from module-declared domain+class only.
- **I-G5:** one projection DTO + one serializer for GUI/REST/CSV; witness refs
  resolve or render explicitly unresolved; caps enforced.
- **I-G6 (mechanism regression):** existing table viewpoints render identically;
  validation rejects unknown constructs with typed errors; previous-release
  viewpoint files load byte-identically.
- **I-G7:** load-time validation covers pattern names/namespace, applies_to,
  enum-set parameter rules, structural caps, and status-rule verdict
  polarity.
- **I-G8 (GUI parity):** every construct the shipped definition uses is
  authorable/editable in the GUI with progressive disclosure; the parameter
  toolbar is visible even with all defaults; GUI validation == loader
  validation.
- **I-G9 (ontology independence):** mechanism imports no specific ontology;
  fixture-module end-to-end test.
- **I-G10 (budgets):** structural caps at load; request-wide budget aborts
  all-or-none with a typed error.

### 10.11 Control structure & UCAs

Loop: modeler → parameterized execution → evaluator (adjacency snapshot +
derivation) → verdicts → modeler creates missing elements → re-execution.

- **UCA-G1** *Verdict provided wrongly* — false pass via existential shortcut
  masks an incomplete required branch (the defining failure this round). [F7.5]
- **UCA-G2** *Verdict provided for a non-applicable row* — requirement shown as
  missing on the motivation column. [F7.15]
- **UCA-G3** *Controls not provided* — defaulted parameters leave no visible
  way to change scope. [F7.16]
- **UCA-G4** *Evaluation runs too long / partial verdicts* under budget
  pressure. [F7.3]
- **UCA-G5** *Mechanism change regresses existing viewpoints or persisted
  files.* [F7.7/F7.17]

### 10.12 Failure modes with S|O|D

| ID | Failure mode | S | O | D | RPN | Primary mitigation |
|---|---|---|---|---|---|---|
| F7.1 | Wrong layer membership → false gaps/passes | 6 | 5 | 6 | 180 | I-G4; census matrix over all common/business/application types |
| F7.3 | Trace evaluation exceeds time or returns partial verdicts | 6 | 7 | 6 | 252 | §10.5 caps + request-wide all-or-none budget; perf acceptance p50/p95 |
| F7.4 | Parameters or pipeline phases not honored end-to-end | 5 | 4 | 5 | 100 | Enum-set validation; pipeline-order integration test (gap beyond legacy limit); parameter matrix (unit + Vitest + e2e); URL snapshot test |
| F7.5 | One complete branch masks an incomplete required branch (false green) | 9 | 8 | 7 | 504 | §10.2 branch-complete quantifiers; the seven-fixture matrix incl. the live branched assurance goal as named witness |
| F7.7 | Existing table viewpoints or saved definitions regress | 5 | 4 | 4 | 80 | I-G6 catalogue regression + previous-release file fixture |
| F7.9 | Witness/branch reporting unbounded or nondeterministic | 4 | 4 | 4 | 64 | DTO caps + stable ordering; fan-in fixtures |
| F7.11 | A `{ref}` expands the wrong branch mapping, or branch evaluation starts from the wrong root entity | 6 | 4 | 6 | 144 | §10.4-only fixtures: same-document expansion, nested references, reference cycles, root-base correctness with multi-witness fan-out |
| F7.12 | GUI authoring produces declarations the loader rejects | 4 | 4 | 4 | 64 | One shared validation implementation; contract test |
| F7.13 | Pattern authoring overwhelms the default GUI surface | 4 | 5 | 5 | 100 | Progressive disclosure; default = pick pattern/set scope; e2e G-S3 |
| F7.14 | Mechanism couples to archimate-4 | 5 | 4 | 5 | 100 | I-G9 dependency-policy + fixture-module tests |
| F7.15 | Non-applicable row rendered as gap | 8 | 7 | 6 | 336 | `applies_to` + `not_applicable` verdict; acceptance fixture |
| F7.18 | Layer diagnostics treated as mandatory conjuncts → systematic false gaps (app-only/business-only/technology-realized requirements flagged) | 9 | 9 | 8 | 648 | §10.2c2: verdict = motivation + overall_realization only; registry-derived eligible set; diagnostic columns `none_observed`; pass fixtures per layer family |
| F7.19 | Mixed no-terminal branch disappears from the denominator → false green | 9 | 8 | 8 | 576 | §10.2c tagged missing-* obligations; incomplete_branch_count gap rule; exact fixture matrix |
| F7.20 | TASKS/PLAN grammar mismatch → executor invents the persisted format | 8 | 9 | 7 | 504 | §10.4 closed schema is the single grammar; caps/tests/sweep reference only its fields; schema-derived shared fixture corpus |
| F7.22 | Diagnostic absence forced into the authoritative verdict shape (misleading pass/false N-A) | 8 | 8 | 7 | 448 | §10.4 discriminated PatternResult union; role-specific CSV columns; app-only fixture serialized identically across GUI/REST/CSV |
| F7.21 | Trace memo key coupled to assurance state → needless invalidation + I-G9 violation | 5 | 7 | 6 | 210 | §10.5 trace-inputs-only key; dependency-policy test; lock-flip non-invalidation test |
| F7.16 | Defaulted declaration executes with no reachable controls | 8 | 9 | 7 | 504 | Always-available parameter toolbar (mechanism); e2e asserts controls visible with all defaults |
| F7.17 | New grammar saved into repo files without declared format impact | 7 | 7 | 7 | 343 | §10.7 + §9.1 row; contract-version compatibility fixtures |

### 10.13 Stories & test strategy

- **G-S1 (owner, worklist):** with `gaps_only` on, exactly the not-fully-realized
  motivation entities appear; the branched assurance goal with one incomplete
  outcome branch **is listed as a gap** with the failing branch identified;
  REQ-C3 appears; witness links navigate; CSV equals the GUI DTO.
- **G-S2 (owner, longitudinal):** after Part A lands, coverage improves without
  viewpoint changes; two executions around a model change prove re-evaluation.
- **G-S3 (author, GUI):** scope/gap controls visible despite defaults; pattern
  authoring one level deeper; edge/shortcut/leaf editing deepest (the
  tagged §10.4 constructs — there are no steps); invalid constructs
  unsubmittable; preview shows one authoritative and one diagnostic cell of
  the row projection for a sample entity.

| Level | Coverage |
|---|---|
| Domain/application unit | The seven semantic fixtures (two-branch one-incomplete goal; two-requirement one-incomplete outcome; convergent paths; zero-branch; cycle; multi-realizer leaf; out-of-scope entity) — first two MUST be gaps (F7.5); applicability (F7.15); enum-set + declaration validation (typed errors, no vacuous cycle tests); verdict polarity + coverage ratio determinism (I-G2/I-G3); namespace collisions; structural caps; budget abort all-or-none (I-G10). |
| Backend integration | Execution over fixtures incl. hidden-branch visibility; previous-release viewpoint file loads unchanged (F7.17/I-G6); definition round-trip + two-executions-around-change + repository scan (I-G1); REST == CSV == GUI DTO; performance runs (p50/p95 recorded). |
| Frontend Vitest | Parameter toolbar with all defaults (F7.16); scope set control; verdict cell rendering (textual status, witnesses, coverage ratio); shared-validation contract (F7.12); progressive disclosure (F7.13). |
| Playwright e2e | G-S1 incl. the named live branched-goal witness; G-S3; URL snapshot reload reproduces results; route-walk smoke. |
| Closure | Live self-model + branching-fixture measurements against the §10.5 thresholds. |

## 10b. Part L — Licensing & legal readiness for open-source publication (publication gate; PRECEDES Part E)

The project is being prepared for **non-commercial open-source publication**. Before the
documentation rework (Part E) presents the project publicly, its dependency and runtime
stack must be shown license-compatible with that publication, and every redistribution
obligation must be discharged. The ArchiMate modelling guidance was already license-separated
and made CLI-importable for exactly this reason (guidance-first, license-separated method
content) — Part L generalises that discipline to the whole stack.

*Not legal advice.* Conclusions here are read from the public license texts and our actual
integration; the publication decision and any ambiguous case are confirmed with counsel. The
engineering job is to make the compatible choice the default and discharge obligations
mechanically.

### 10b.1 Order of work (owner-directed)

The **native/runtime setup is checked first** — if the platform (Docker image, the JVM,
Graphviz, PlantUML, git) is not cleanly compatible, no amount of Python/TS package hygiene
matters. Only then the language-ecosystem package sweeps.

### 10b.2 Setup-level determinations (verified against our integration 2026-07-22)

| Component | How we integrate | License (as used) | Exposure | Adopter-friendly disposition |
|---|---|---|---|---|
| **PlantUML** `1.2026.3` | `plantuml.jar` **bundled** in the image (fetched by `get-plantuml` from Maven Central / GitHub releases); invoked **arm's-length** as a separate process (`subprocess java -jar`) | plain `net.sourceforge.plantuml:plantuml` artifact = **GPLv3** | We do NOT link it (separate process → no derivative work), but we **redistribute** the GPL jar in the image | **Switch the bundled jar to a permissive/weak-copyleft variant** published on Maven Central — `plantuml-mit-light` (filtered MIT), `plantuml-lgpl`, `plantuml-epl`, or `plantuml-bsd` — after verifying our diagram-type usage renders identically. Removes/*minimises* redistribution copyleft entirely. Pin the variant in `get-plantuml`. |
| **JRE** | `default-jre-headless` installed in the image; runs PlantUML | OpenJDK = **GPLv2 + Classpath Exception** | Bundled + run | Keep bundled OpenJDK (works out of the box; the Classpath Exception is designed for exactly this). **Add a user-settable JRE** escape hatch (honour an explicit `JAVA`/`JAVA_HOME`/settings path) for adopters who must supply their own compatible JRE. |
| **Graphviz** | `graphviz` apt package; PlantUML shells out to `dot` | **EPL-1.0** (weak copyleft) | Bundled + invoked | Compatible; ship the EPL notice + attribution. We do not modify it. |
| **git** | apt package; invoked as a separate process for repo sync | **GPLv2** | Invoked, not linked; standard base-image package | Aggregation/arm's-length — compatible; notice in the third-party inventory. |
| **Base image + fonts** | Debian-based Python image + font packages | per-package (Debian main = DFSG-free) | Redistributed in the image | Inventory the base image's shipped licenses; ship font licenses (OFL/etc.); confirm no non-free package pulled in. |

**Key finding:** the only genuine copyleft-redistribution exposure is the **GPLv3 PlantUML
jar**; switching to a published permissive variant is the efficient, robust, adopter-friendly
fix and is the load-bearing decision of WU-L1.

### 10b.3 Package-sweep approach (Python + TypeScript)

Automated, reproducible, CI-enforced — not a one-time manual read. Produce a **license
inventory artifact** per ecosystem (tool-generated: e.g. `uv`/`pip-licenses` for Python,
`license-checker` for npm), classify each into allow / notice-required / review / deny
buckets against the chosen publication license, and fail CI on a deny or an unknown. The
inventory is committed so drift is a reviewable diff.

### 10b.4 Obligations discharge

A single top-level **`THIRD-PARTY-NOTICES`** (generated from the inventories) plus the bundled
runtime notices (PlantUML variant, Graphviz, OpenJDK, fonts) shipped in the image and the
source tree; the project's own **LICENSE** (the chosen non-commercial OSS license); and a
short **licensing reference page** (authored in Part E's docs pass, stub created here). Any
weak-copyleft bundled component (EPL/LGPL) gets its written-offer/notice satisfied by shipping
its notice and pointing at its upstream source.

### 10b.5 Invariants

- **I-L1:** no bundled or redistributed component carries a license incompatible with the
  chosen publication license; the only permitted copyleft is arm's-length-invoked (separate
  process) or weak-copyleft-with-notice.
- **I-L2:** every third-party component we ship or invoke appears in the committed inventory
  with its license; CI fails on an unknown/denied license.
- **I-L3:** obligations (notices, attributions, source offers) ship **in the artifacts adopters
  receive** (image + sdist/wheel + repo), not just in a doc.
- **I-L4:** the compatible choice is the **default**; escape hatches (user-settable JRE) never
  silently reintroduce an incompatible default.

### 10b.6 Acceptance

The bundled PlantUML jar is a permissive/weak-copyleft variant (or the GPL redistribution is
explicitly discharged with notice + source offer, decision recorded); committed Python and
npm license inventories with a green CI license gate; a generated `THIRD-PARTY-NOTICES`
shipped in the image and source tree; the project LICENSE chosen and present; a user-settable
JRE path honoured with the bundled OpenJDK as default; every setup-level component in §10b.2
dispositioned with evidence.

## 11. Security & classification considerations 🔴

- **Proportionality (governing posture).** This product is security- and
  safety-conscious but is not (yet) built for extreme confidentiality regimes
  (critical infrastructure, defense, hazardous biotech analyses). The **hard
  invariants** are the structural ones: the one-way persistence rule (nothing
  confidential or signal-derived under any repository path), the TLP ceiling on
  every read path, unlock gating, and audit. **Session-level residual exposure to
  the already-authorized local user** (e.g. content still on screen after a
  user-initiated lock) is accepted; no purge/subscription machinery, memory
  scrubbing, or equivalent high-assurance measures. New requirements drifting in
  that direction need an explicit owner decision first.
- Both parts extend the **read surface** of confidential content: every new endpoint
  (neighbors, catalog-driven search, metrics) goes through the exposure policy and
  unlock gate per the §6.0(a) matrix and D7 (edge-catalog is configured-gated;
  the deprecated public backend answers `no_active_run`; everything else
  unlock-gated); error/absence semantics must not distinguish "locked",
  "above ceiling", and "unknown id" in ways that leak existence (align with the
  established locked(423)/forbidden/empty contract).
- Part C creates a **new derivative channel** for confidential data (colors on
  architecture diagrams). D11 + I-C1 are the containment: ephemeral render only,
  refusal on persistence, exclusion from exports, no-store headers, redacted logs.
- The refresh script handles only the product's own dependency data (TLP:AMBER
  ceiling respected by the store); OSV queries disclose the dependency list to
  osv.dev — acceptable for this project (public OSS dependencies), noted explicitly.

## 12. Questions — resolved (single authoritative ledger; TASKS references
this section and adds nothing)

- **Q1 → decided:** core metric set with the direct-vs-transitive split applied to
  **component findings** (`open_component_findings` partitions by directness;
  `distinct_open_vulnerabilities` does not partition); `max_cvss_score` from
  parsed vectors only; **no KEV in v1**; no dependency-depth number. EPSS is
  recorded as a **draft** motivation-domain requirement (REQ-C3), not implemented.
- **Q2 → decided (superseded into D9):** the **active completed refresh run** per
  anchor is the metrics basis; BOM serial/version are provenance metadata only;
  run history retained (v1: no automatic deletion — §6.0.c); basis run +
  timestamp surfaced.
- **Q3 → decided:** `Platform Adopter` stays engagement-local; promotion revisited
  when publication planning makes the persona real (the broader
  stakeholder-reference question remains in the backlog).
- **Q7 → decided, then superseded in part by Q8:** gap cells show declared
  missing expectations + last-satisfied witnesses; `requirements-coverage-gaps`
  is kept and cross-referenced. The three-state/three-boolean shape was
  replaced by Q8 (branch-complete row projection; set-valued `scope`).
- **Q5 → decided (attribute sets):** business-object = Meaning/Provenance/
  Contained Information/Internal+External Consistency Criteria + Sensitivity
  enum + Lifecycle States list; Service = five lists/strings + Source
  Repository (uri, informative) + Lifecycle State enum; Module = Problem
  Domain + Lifecycle State (no Owner); Endpoint = Communication Protocol &
  Version + Authentication Method + Lifecycle State (§7.1b is the exact
  payload contract).
- **Q6 → decided (second review), partially superseded:** the surviving parts —
  refresh orchestration = single `RefreshSecuritySignals` use case with
  CLI-only adapters; run identity/retention per §6.0(c); VEX key per §6.0(d);
  traversal size-budget partials + whole-request time abort, no continuation;
  synthetic media = TLP:WHITE. Superseded parts: the audit policy is now D21
  (not "unlock + audit-failure fails mutation") and guidance migration is the
  §9.2 one-line header text patch + sidecar fields (not a "wrap").
- **Q9 → decided (fourth review):** shortcut edges = direct stored
  `archimate-influence` only (§10.2b); generic association → `ambiguous_link`
  diagnostic gap, never asserted realization.
- **Q12 → decided (owner scoping):** the self-model + assurance store are
  pre-publication example content — no real confidentiality, no third-party
  legacy. The dev store migrates/recreates freely; WU-B0's
  repair-vs-grandfather default for the dev store is **repair/recreate**
  (grandfathering machinery exists for future users, proven on fixtures);
  Part F's previous-release fixtures are synthetic by construction (they model
  pre-release formats, not a protected user store); the supported migration
  floor for the operational stores starts at this release. Product invariants
  (one-way persistence, TLP ceilings, fail-closed media harness,
  quarantine-not-fabrication) are unchanged — they are what the product ships,
  exercised through dogfooding discipline.
- **Q11 → decided (sixth review):** public-SQLite migration is
  **administrative-only**: TLP:WHITE legacy rows quarantine in the public
  file; any above-WHITE row is a blocking preflight finding (commit writes
  nothing to that target; report carries table/PK metadata only, never raw
  payload; manual path = secure import into the co-located store or verified
  purge); the public file is permanently `no_active_run` in v1 — no refresh
  instruction exists for it.
- **Q10 → decided (fourth review):** public SQLite metrics **deprecated in v1**
  (§6.0(a)) — no population path exists; upgrade finding directs to co-located
  SQLCipher; snapshot-publication command is the documented future path.
- **Q8 → decided (third review):** branch-complete full realization (§10.2);
  D21 audit durability option 2 (co-located single-transaction data+audit;
  public SQLite read-only v1); `scope`+`gaps_only`+`group` parameters with the
  §10.3 enum-set/pipeline contract and always-visible controls; shortcut = gap; executed
  table, never a saved diagram; viewpoint grammar in the §9.1 migration table.
- **Q4 → decided:** styled-render download allowed only via the D11 export
  pipeline, stamped with the **computed classification**, basis run, and
  timestamp (I-C8); git/repo persistence stays refused.
- **Q13 → decided (owner walkthrough against `spec/STPA_Handbook.pdf`):** the
  assurance relationship model is reconciled as specified in D6 — UCA/CAC stay
  reified nodes (five-part UCA format; UCAs carry their own traceability);
  UCA→hazard = `leads-to`, `violates` and `satisfied-by` dropped;
  `responsible-of` → `responsible-for` (CSN→constraint), `accountable-to` →
  `accountable-for` (owner→risk, direction flipped); risk owner = organizational
  control-structure-node with optional role binding; `evidence` = declared node
  type with optional-but-flagged `binds-to` binding to implementing ArchiMate
  entities; new derives/leads-to/refines rows per D6; matrix enforcement =
  **exhaustive**; `stpa_complete`/E502/`grc_complete` updated to match; dev
  store repaired per Q12 (deterministic repairs = U0 data migrations).

## 12b. Authoritative vocabulary (TASKS/PROMPT reference this — never restate)

| Concept | Authoritative form |
|---|---|
| Run lifecycle | `staging → complete → active → superseded`; `staging → failed` terminal (§6.0c) |
| Run identity | unique `run_id`; `IdempotencyKey = (anchor, request_id)`; `request_payload_digest` = SHA-256 of the canonical bundle (NOT the BOM digest); mismatch = typed no-write conflict (§6.0c table) |
| VEX key | `(anchor_entity_id, canonical_component_id_incl_version, canonical_vulnerability_id)` (§6.0d) |
| Snapshot | opaque `SignalSnapshotToken` (§6.0f) |
| Mutation capability | §6.0(a) predicate over store × signals × archive × lock |
| Public sqlite | metrics deprecated in v1 (Q10): `no_active_run`; migration finding; admin quarantine inspection only |
| Guidance migration | one-line cache-header text patch + sidecar field update; all other bytes preserved (§9.2) |
| Viewpoint parameters | `scope` enum-set + `gaps_only` + `group` (§10.3a) |
| Verdicts | `pass | gap | not_applicable` + §10.2d registry; row verdict = motivation + overall_realization; layer columns diagnostic (`none_observed`) |
| Trace edges | branch = direct stored realization (+ influence shortcut; association→ambiguous_link); leaf = direct+derived realization; grammar = closed `branch-complete-realization` kind (§10.2/§10.4) |
| Table persistence | executed table; definition persists, cells never (§10.6) |
| Format impact | viewpoint grammar, stores, cache, deployment settings/config = §9.1 rows |
| Upgrade CLI | additive: existing flags/guards kept; dry-run default; exit 3 preserved; new 20/21; DeploymentLayout resolver |
| Failed-run replay | terminal; same key+digest returns stored outcome, never resumes; different digest = conflict (§6.0c table) |

## 13. Acceptance criteria (objective, layered)

### 13.1 Per-part criteria

Part A:
1. Strategy domain populated per §4.4 as **deltas over pre-execution live stats**
   (+5 CAP, +3 COA, +4 RES, +4 VS, +18 stages, +4 VAL, +1 STK in group
   `strategy-and-value`) — never asserted against absolute historical totals.
2. All §4.6 diagrams exist and every post-render assertion in the §4.6 table is
   checked and recorded; the resource-map heat-map shows `investment_level`
   banding with no fallback warning (requires WU-A0).
3. `artifact_verify` clean (0 errors; no new warnings on created entities).
4. Witness chains **W1 and W2** verified hop-by-hop per §4.9 (types + directions),
   and W1 additionally confirmed as derived reachability by the derivation engine.

Part B:
5. Assurance node detail and edge lists show name-resolved, clickable endpoints;
   edges with a non-visible endpoint are **absent entirely** (no placeholders, no
   counts — I-B1); integration matrix over mixed-TLP fixtures proves it; the only
   policy signal is the coarse `visibility_limited` flag.
6. `/api/assurance/neighbors` honors hop/node/edge budgets with typed
   truncation + frontier node IDs and aborts whole-request on the time budget
   (no continuation tokens), is cycle-safe and deterministic; the assurance
   graph view walks B-S2 in e2e.
7. WU-B0 deliverables exist and are recorded: completed-or-advisory matrix
   decision, read-only store preflight report, repair/grandfather decision; GUI
   picker options equal the loaded module catalog (contract test) and server-side
   validation matches the WU-B0 decision.
8. `/assurance/node/:id` deep-links resolve; unknown id and above-ceiling id are
   indistinguishable.
9. After a mid-session lock, every subsequent Part B request returns the locked
   status and the GUI collapses on its next fetch/navigation (integration +
   Vitest; no purge machinery — §11 proportionality).

Part C:
10. One refresh run per anchor staged, completed, and atomically activated;
    the crash-before-activation test leaves the previous run active; re-running
    creates a new run; `assurance_security_stats` reflects both anchors.
11. Metrics tool/REST/dashboard/provider/detail-panel return identical numbers
    from the same active run (cross-surface test), with per-directness finding
    counts summing to the finding total (I-C9), alias-deduplicated distinct
    vulnerabilities, and basis run + timestamp + computed classification in every
    payload.
12. C-S3 in e2e: unlocked colored render; locked → default styling + note;
    persistence refused by viewpoint semantics; stamped export via the D11
    pipeline with computed-classification banner.
13. No **operational** signal-derived value in any git-tracked file after the
    full e2e suite: denylist text scan over text files, harness provenance for
    all media (I-E1/I-E3), and the I-C1 regression tests — visibly marked
    synthetic fixtures are the only permitted signal-shaped content.
14. C-S2 in e2e/integration: a contextual VEX assessment is recorded through the
    audited mutation, suppresses exactly its keyed finding, leaves other anchors
    untouched, and appears in the audit log.
15. D17 panel: read-only with offset background + computed classification icon +
    basis; hidden when locked/unanchored; edit round-trip on a metric-bearing
    entity leaves persisted properties byte-identical (F3.13, two levels).

15b. §6.0(a) matrix parity for operations exposed on multiple transports
    (delegation tests), plus negative tests asserting the refresh lifecycle is
    absent from REST/MCP (deliberately CLI-only); the refresh script passes the
    no-infrastructure-import dependency test and drives the single
    `RefreshSecuritySignals` command; D21 fault-injection matrix green at every
    commit boundary.

Part F:
19. The §9.1/§9.2 contracts are implemented end-to-end: a previous-release
    workspace (tier repos, v1 guidance cache + sidecar, legacy SQLite signals,
    legacy SQLCipher assurance data, pre-grammar viewpoint files) upgrades
    through the public CLI; the default dry-run invocation writes nothing
    anywhere; a blocker in the
    last discovered target prevents all writes; an injected apply failure after
    one committed target yields an accurate partial report and a safe resuming
    rerun; locked SQLCipher is blocking with credentials only via the
    non-interactive path (never logged); Docker startup upgrades mounted
    previous-release volumes before ordinary connector initialization and
    reaches healthy; a fresh deployment initializes absent stores at current
    version without claiming a migration; quarantine schema populated exactly
    once across reruns; `FORMAT_CONTRACT_VERSION` bumped with coverage tests
    green; §9.4 self-model delta verified with query witnesses.

Part D:
16. Guidance v2 live: a strategy-domain request returns domain-level framing once
    plus type litmus lines; a v1 fixture imports and serves unchanged; the
    v1-shaped output subset is structurally identical to the pinned fixture; the
    real-extract restructure + `--strict` re-import is recorded at the owner
    checkpoint.
17. Schemata ship on the existing `attributes.<type>.<specialization>.schema.json`
    convention through the existing resolver (a test proves validator, GUI editor,
    and registry snapshot delegate to it); ENG-ARCH-REPO and the enterprise repo
    gained exactly the missing files (incl. `attributes.resource.schema.json`),
    pre-existing files untouched; startup schema validation green; `Architecture
    Backend` is Service-specialized with its attribute set filled via MCP.

Part E:
18. §8.4 checks green: every image from a named deterministic test, no live
    assurance connector during capture, synthetic data visibly marked, stable
    IDs, alt text, link + generated-reference checks, README claim amended,
    manual visual review done.

Part G:
20. The §10.3/§10.4 mechanism works: the shipped declaration passes production
    authoring validation under the default parameter cap; the parameter toolbar
    is visible with all defaults; each `scope` choice changes the evaluated
    population; the §10.3b pipeline order holds — a gap beyond any legacy
    pre-trace limit still appears under `gaps_only`, and gaps-first sorting is
    global, not page-local; `gaps_only` filters exactly `verdict = gap` (N/A
    rows never shown as gaps); `scope` round-trips YAML/JSON/URL with
    duplicate/reorder canonicalization; a copied URL reproduces the parameter
    snapshot and result; GUI, REST, and CSV carry the same row projection DTO
    (authoritative verdicts vs diagnostic observations, role-specific
    namespaced `trace:`/`param:` columns); invalid parameters/types/names
    fail at load with typed errors (unit + Vitest + e2e evidence).
21b. GUI parity (I-G8): G-S3 walked in e2e; one shared validation path proven
    by contract test; the mechanism passes the fixture-module ontology-
    independence test and the dependency-policy gate (I-G9); budgets abort
    all-or-none with typed errors (I-G10); previous-release viewpoint files
    load unchanged and the format-impact contract of §10.7 is fixture-tested.
21. `motivation-coverage` renders over the live self-model with the §10.2
    semantics: the full fixture matrix passes — goal w/o outcomes, goal w/ two
    outcomes one lacking requirements, outcome w/o requirements, complete
    outcome + uncovered requirement, retired-only child (ALL gaps); shared
    requirement under two outcomes = two obligations; app-only,
    business-object-only, and technology-realized requirements PASS overall
    (F7.18); influence-shortcut detected on the live witness while association
    yields `ambiguous_link`; requirement-row overall verdict agrees with
    `requirements-coverage-gaps`; verdict cells carry textual status, coverage
    ratio + incomplete_branch_count, bounded witnesses, realizer_layers;
    gaps-first ordering; REQ-C3 appears as a gap; executed-table semantics per
    §10.6; docs cross-reference `requirements-coverage-gaps` both ways.

### 13.2 Layered gates

- **Local:** pure permutation tests for package identity / affected ranges / CVSS
  parsing / VEX keying; schema and guidance-hierarchy validation; traversal
  bounds and deterministic DTO ordering; static specialization attributes never
  mix with derived attributes.
- **Regional:** one refresh is atomically visible across MCP, REST, dashboard,
  viewpoint, and detail page; lock/ceiling/run changes produce all-or-none
  results; GUI catalog choices are a subset of the same module policy enforced on
  writes; validator, editor, and registry snapshot use the same effective schema;
  each strategy diagram answers its declared §4.6 question.
- **Global:** no above-ceiling identity, count, or topology leakage; no
  operational signal-derived value under any repository path, screenshots
  included; synthetic documentation data is visibly marked and cannot reach
  production persistence; architecture and assurance repositories verify cleanly;
  README, docs, reference, and screenshots describe the same current product
  (truth audit compares them against the running UI/API contracts and generated
  MCP tables — not file existence); a **cross-document semantic consistency
  check** over PLAN/TASKS/PROMPT: the rejected-vocabulary sweep (include_goals /
  include_outcomes / include_requirements / "full | shortcut | missing" /
  "no Part F impact" / "not a persisted-surface migration" / "mechanical
  wrap" / "snapshot tuple" / "component/finding" / stale KEV / hardcoded
  classification / latest-serial / universal-lock / single-query-trace — plus
  the trace-grammar checks: no `steps/alternative`, no `quantified step`, no
  `step-chaining`, no `step editing`, no authorable `alternatives` or `status
  rules`, no load-time graph fan-out, no undifferentiated "one verdict DTO" OR
  "the verdict DTO" in active Part G instructions, no public above-WHITE
  `block/quarantine`) returns
  ONLY explicitly-labeled rejected-design history, plus a human semantic read
  for conflicts a text search cannot catch; previous-release upgrade fixtures pass (§9); full test,
  lint, type, and dependency-policy gates pass once over the integrated result.

## 14. Out of scope

- Composition roll-up of metrics (platform = max over parts) — design note only.
- EPSS/exploitability **implementation** (intent recorded as draft REQ-C3);
  CISA-KEV ingestion and any `kev_count` metric; dependency-depth numbers;
  auto-scheduled scanning/CI.
- Assurance **edge editing** (create + delete only in v1); edge diff/versioning
  views; sealed-baseline graph exploration.
- A one-query component→persona trace projection (witness chains serve v1 — §4.9);
  weakening derivation rules is forbidden, not merely out of scope.
- Guidance hierarchies for diagram-type modules (ontology modules only in v2).
- General computed-cell expression language for viewpoint tables; dynamic
  (ontology-derived) expected-type inference; raw graph-leaf frontiers
  (rejected as fuzzy); a dedicated pattern-condition criteria node and
  column-level pattern conjunction (audited, deleted as redundant); a
  persisted "table application" artifact and a rendered gap *diagram*
  (separately scoped future features — §10.6); leaf-realizer multiplicity
  policies (existential leaf in v1 — §10.2).
- Any architecture-ontology change; any GTM/marketing strategy content (D1).
- Multi-BOM union or active-flag semantics beyond the run model (D9).
- Purge/scrubbing machinery for already-rendered confidential content (§11).
- Transactional audit-intent outbox; any public-SQLite signal capability in v1
  (metrics deprecated per Q10; the snapshot-publication command and the outbox
  are the documented future paths — §6.0(a));
  public REST/MCP refresh lifecycle API (CLI-only command adapters in v1 —
  §6.0(b)).
- Server-side traversal continuation tokens (D7); refresh-run pruning/retention
  automation (§6.0(c)); OSV commit-event range evaluation (§6.0(g)).
