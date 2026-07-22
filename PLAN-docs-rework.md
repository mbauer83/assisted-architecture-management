# PLAN — Documentation rework (E1 evaluation + execution plan)

Owner-review document for the documentation stream of
`PLAN-strategy-and-assurance-uplift.md` (Part E, §8.1). Produced 2026-07-22 from a fresh
survey of every docs page (headings + last-commit dates), the README, the ledger's
reconciled state, and a live walk of the self-model (472 entities / 1013 connections /
40 diagrams; 37 viewpoints in the effective catalog). **No docs have been edited yet** —
execution starts only after this plan is approved.

Companion facts used throughout:
- The docs were NOT uniformly abandoned: pages touched alongside recent streams are
  current (e.g. `viewpoints.md`, `security-signals.md`, `schemata-and-profiles.md`,
  `aibom.md`, `coverage-semantics.md`, `interfaces-and-mcp.md`, `mcp-tools.md`,
  `storage-and-confidentiality.md` — all 2026-07-21/22). The gap is concentrated in
  **missing pages** (strategy, upgrade guide, showcase, guidance v2, REST/OpenAPI,
  licensing body) and a handful of **stale pages** (installation 06-22, projects 06-13,
  document-types 06-13, assurance diagrams 06-22, docker-compose 07-13,
  ontology-modules 07-13).
- E2 (screenshots) is restart-gated; this plan fixes the shot list + IDs now (§3) so E1
  prose can reference media slots deterministically.

---

## 1. Gap analysis — capability by capability

Verdict legend: **NEW** = new page · **EDIT** = targeted edits to an existing page ·
**MENTION** = a cross-link/paragraph elsewhere suffices · **VERIFY** = page looks
current; re-read against code during execution and touch only if drift is found.

| # | Capability | Current docs state | Verdict |
|---|---|---|---|
| 1 | **Strategy & value self-model** (capabilities, value streams/stages/values, courses of action, resource-investment heat map) | No dedicated page — deliberately so: strategy is an ordinary ArchiMate domain, and no other domain (business, application, technology) has a per-domain page either. The generic modeling pages cover authoring; the four strategy viewpoints (capability-map, resource-map, strategy, value-stream) are self-describing in the viewpoint catalog. | **MENTION** — strategy viewpoints + the resource-investment heat map (incl. the resource-map/capability-map styling asymmetry) get a short worked-example mention in `viewpoints.md`'s existing styling/worked-examples sections; the strategy *self-model* is shown in the showcase (§1.2), not documented as a feature |
| 2 | **Assurance explorability** (edge enrichment, ontology-driven edge authoring, neighbor traversal, shared graph-explore canvas, deep-linkable node route) | `04-assurance/diagrams.md` (06-22) predates all of it; `gui-capability-design.md` (07-21) covers the *design*, but it is a design/explanation doc, not user documentation. `diagrams.md`'s statement that its figures are the project's **own STPA-Sec analysis** is correct under the media policy (§3.0) and stays. | **NEW** — `docs/04-assurance/exploring-assurance.md` (browse/detail/graph traversal only); **EDIT** `diagrams.md` (cross-link + refresh for the current viewer surfaces) |
| 2b | **Assurance authoring workflow** (create an analysis, guided method wizards, completion review, seal a baseline) | Undocumented as a task path: `methods.md` explains STPA/CAST/GRC concepts and completion checks, and the assurance index promises "wizards", but no page walks creating an analysis, using a wizard, reviewing gaps, or sealing a baseline — all real surfaces (GUI routes for STPA/GRC/CAST/GSN/supply-chain/analysis-browse/baselines; MCP create/update/delete + seal). | **NEW or EDIT** — one method-workflow guide (expand `methods.md` or a sibling how-to page): analysis creation, the guided workflows, completion review, baseline sealing |
| 3 | **Security signals & virtual attributes** (refresh-run lifecycle, posture metrics, VEX, OSV/CVSS acquisition + `tools/ingest_security_signals.py`, `security-posture` viewpoint, entity derived-attributes panel, both signal backends) | `security-signals.md` (07-21) covers snapshot produce/read, identity, directness, storage — but its headings show **no VEX section, no refresh-run lifecycle, no security-posture viewpoint, no derived-attributes panel, no backend-configuration matrix**. | **EDIT** (substantial) `security-signals.md`; backend configs go to `reference/configuration.md` (EDIT); deprecation/migration guidance for the public backend belongs in the upgrade guide (#9), not normal configuration |
| 4 | **Guidance pluralism v2** (hierarchy-generic guidance + domain context, default schemata, `arch-import-guidance` flow) | `ontology-modules.md` § "Guidance externalization" is 07-13, pre-D1 (v2 landed 07-21). `cli-and-backend.md` has a "Guidance import" section (07-21, likely current). | **NEW** — `docs/05-extensibility/guidance.md` (pull guidance out of ontology-modules into its own page: format v2, ancestor/domain context, composition, default schemata, import flow, cache upgrade posture); **EDIT** `ontology-modules.md` to slim + link |
| 5 | **Motivation-coverage viewpoint** + coverage semantics | `coverage-semantics.md` (07-21) is current and exactly the §10.2 semantics page E1 asks for, including the false-green example. | **VERIFY** + cross-link from `viewpoints.md` and the showcase; do **not** duplicate |
| 6 | **Viewpoints query model** (typed let-bindings, derived relationships/impact, traversal authoring, witness-chain sidebar) | `viewpoints.md` (391 lines, 07-21) + `reference/viewpoints-schema.md` (609 lines, 07-21) + `impact-analysis.md` (07-14) — all shaped after the bindings/derivation plan completed. | **VERIFY** (witness-chain sidebar + traversal-authoring UI presence; add if missing) |
| 7 | **ArchiMate 4.0 conformance**, specializations, C19C exchange | `reference/archimate-4-conformance.md` (07-14) postdates the compliance plan's completion (07-12). Specializations covered in `ontology-modules.md`. | **VERIFY** |
| 8 | **Attribute-profile registry** (named profiles, blast-radius failure semantics) | `schemata-and-profiles.md` (07-22) has "Named attribute profiles" + "Failure semantics" sections — written this week. | **VERIFY** |
| 9 | **Upgrade/repair** (`arch-repair upgrade`, format-contract versioning, migrators) | `cli-and-backend.md` already documents the command surface in depth (~100 lines: flags, exit codes, deployment identity, per-target backup/recovery, resumability, supported floor). What is missing is a task-oriented operator walkthrough. | **NEW** — `docs/reference/upgrade-guide.md` (see §1.1): **move** the operational narrative there from the CLI page (no duplication); the CLI page keeps command syntax, flags, exit codes + a link |
| 10 | **AI-BOM** (model-derived) | `aibom.md` (07-22) — current. | **VERIFY** |
| 11 | **OpenAPI / REST contract** | `reference/rest-api.md` already documents `/docs`, `/redoc`, `/openapi.json` and the contract-test-enforced fidelity guarantee for the modeling/query surface (contract test passes). Its "Deferred" section is accurate: assurance/promotion/sync/admin/events endpoints genuinely remain at FastAPI defaults. | **VERIFY** — keep the explicit deferred boundary unless the code proves those families have also landed |
| 12 | **Licensing & setup** | `reference/licensing.md` is an explicit stub (07-22); good skeleton already (MIT, notices, inventories, PlantUML/JRE). | **EDIT** (expand stub): CI gate workflow, `ARCH_JAVA` resolution order (env → `JAVA_HOME` → `java`), dependency-change procedure, dependency-CVE posture; cross-link from installation |
| 13 | **Deployment** (Docker Compose, entrypoint, profiles, assurance opt-in) | `docker-compose.md` (07-13) predates: `slim-trixie` base, entrypoint upgrade-before-serve ordering, `ARCH_SETTINGS_PATH` vs `ARCH_SETTINGS_FILE` host/container mapping. | **EDIT** |
| 14 | **Navigation, tier facets, workflow/status controls** | `views-and-exploration.md` (07-18) documents the tier facet, but the repository workflow/status cluster is not described — and screenshot S1 is supposed to prove both. | **EDIT** — document the workflow/status cluster (explicit B2 deliverable); verify GAR-free search coverage in the same pass |
| 15 | **Installation** | `02-installation.md` (06-22) is the stalest load-bearing page: predates `ARCH_JAVA`, guidance-import as a setup step, assurance fresh-install UX (`arch-assurance init && arch-assurance seed --with-signals`), refresh-tooling prerequisites, license-gate tooling. | **EDIT** |
| 16 | **Self-model showcase** (strategy → architecture → assurance → security posture walk) | Does not exist. | **NEW** — `docs/06-showcase.md` (see §1.2) |
| 17 | **MCP reference tables** | `interfaces-and-mcp.md` + `04-assurance/mcp-tools.md` both 07-22; a generator with `--check` exists. The `assessed_entity` read-surface rename is **verified live** (backend restarted before this session; `assurance_security_stats` returns `assessed_entity_count` + `assessed_entities`). The rows deliberately carry `entity_id` without `entity_name`: resolving names would cross the assurance↔architecture subsystem boundary, which is kept closed for security. Docs must present this as designed behaviour (resolve names via `artifact_query_read_artifact`), not a gap. | **Run `uv run tools/generate_mcp_docs.py --check`** once, in B1 |
| 18 | Projects & grouping / document types | 06-13 — oldest pages; grouping semantics have since gained tier facets and the group-naming promotion default. | **EDIT** (light) |
| 19 | Motivation page + README | See §2 and §4. | **EDIT** |
| 20 | `docs/architecture/` set | `dependency-policy.md` carries a burn-down table keyed to plan-phase/WU vocabulary whose categories are obsolete (the live baseline holds three different datatype dependencies); `glossary.md` promises a reconciliation in the same vocabulary. Both violate the no-plan-refs rule for persistent docs. | **EDIT** — restate the burn-down against the *current* baseline content with no plan vocabulary; resolve or drop the glossary reconciliation note. `gui-capability-design.md` arrives here too (§2), but **rewritten, not moved as-is**: its "current implemented surface" table and "required use cases" read as future prerequisites that the shipped GUI routes now disprove — convert it to a design-decision record with an implementation-status note and links to the current user docs |

### 1.1 New page: `docs/reference/upgrade-guide.md` (operator guide)

Per §8.1: target discovery (`UpgradeTarget` kinds in operator terms), check vs commit,
credential requirements per target, backup guidance, quarantine semantics, partial
completion + resume, Docker startup ordering (entrypoint upgrades before serving),
report examples **from a synthetic previous-release fixture** (paths/secrets redacted —
reuse the `tests/support/previous_release_deployment.py` shape), the
`signals_backend=encrypted` alias migration and public-backend deprecation, and the
"locked store = unresolved migration, never current" rule. This is also where the
public-sqlite legacy-row policy (blocking preflight finding, secure-import-or-purge)
gets its operator-facing wording.

### 1.2 New page: `docs/06-showcase.md` (self-model tour)

A guided read in **two parts** — the architecture model, then the assurance capability
over it (the boundary the product itself draws between the git-tracked model and the
separately-stored assurance content):

**Part 1 — the public self-model** (every step names the real entity and the surface to
see it on; the chain below is verified against the live graph — pin these exact IDs):

1. Driver `DRV@1776628131.GR9prv` (AI-Assisted Development as Dominant Production Mode)
   with assessment `ASS@1776628140.s68vVo` (LLM-Based Agents Cannot Effectively Use
   Unstructured Architectural Knowledge);
2. → goal `GOL@1712870400.Po1Qw3` (Maintain Coherence and Traceability), realized via
   outcome `OUT@1712870400.LrpdG0` (Increased Architectural Coherence);
3. → course of action `COA@1784483697.FI0Xbj` (Dogfood via the Recursive Self-Model,
   influencing the outcome), realized by capability `CAP@1784482403.pLMHKe`
   (Architecture Knowledge Management);
4. → value stream `VS@1784483014.xrSjjJ` (Model & Validate the Architectural Design),
   served by that capability;
5. → the C4 progression of the platform itself (context → containers → backend
   components, IDs in §3 S5);
6. → from the Architecture Backend (`APP@1777293133.OYEmP1`) into one of its linked
   ADRs via entity backlinks (e.g. the unified-backend decision) — demonstrating
   document authoring and backlinks with no extra screenshot.

**Part 2 — the real assurance self-model:** the STPA-Sec analysis
`STPA@1784721732.pflr.3e4395` (PlantUML Preprocessor Untrusted-Input Disclosure) bound
to the Architecture Backend — an actual shipped security fix, analyzed with the
product's own method tooling — then the security-posture view, the locked-store state,
and a stamped export. Synthetically augmented findings, where used for richer visuals,
carry the marker per §3.0.

This page is the home of the "the model documents itself" claim — which now extends to
the assurance layer: the platform's own hazard analysis, made with the platform. It is
also where the platform's own strategy model (capabilities, value streams, values,
courses of action) appears — as showcase content, not as feature documentation.

## 2. Structure & IA

**Assessment.** The current tree is a numbered narrative arc (01 motivation → 02 install
→ 03 modeling → 04 assurance → 05 extensibility) + `reference/` + `architecture/`.
Against Diátaxis: `reference/` is clean reference; 01 is explanation; 02 is how-to; 03–05
mix explanation and how-to *within* pages, which for this project is a feature — each
page explains a concept then shows the real surface, which matches the grounding rule
(real code + CLI/MCP + real GUI, dogfooded).

**Recommendation: keep the numbered tree; do NOT re-shuffle into literal Diátaxis
top-level folders.** A wholesale reorganization would churn every inbound link and git
history for zero reader benefit at this scale (~30 pages). Instead:

1. Add the missing pages inside the existing sections (§1) + the showcase as `06`.
2. Make each index page state what kind of page each link is (concept, guide,
   reference) — Diátaxis as signposting, not as folders. `docs/index.md` additionally
   gets four audience entry paths: new modeler → first-engagement tutorial; architect →
   modeling/viewpoints/promotion; safety/security analyst → assurance methods +
   confidential storage; AI-agent operator → MCP setup, guidance import, verification,
   authorization boundaries.
3. Move `04-assurance/gui-capability-design.md` → `docs/architecture/` — rewritten per
   §1 row 20 (design-decision record with implementation-status note), never a bare
   relocation; keep a pointer.
4. `docs/index.md` gains the new assurance-explorability page, guidance, upgrade guide,
   licensing, REST/OpenAPI, and the showcase; Reference block ordered: configuration,
   CLI, upgrade, git-sync, docker, REST, viewpoints-schema, conformance, licensing.

**README role:** stays a concise hub — hero, "is this for you", capability table,
quickstart, doc map, status, roadmap, license. Capability-table delta: add an
**Operational upgrades** row only; the existing typed-graph row already spans
motivation → strategy → … → technology, so strategy gets no separate row (consistent
with no per-domain documentation).

**README roadmap section (new):** a short "Roadmap" section next to Status — five
one-line bullets, explicitly framed as directions under consideration, not
commitments (which keeps it compatible with the no-aspirational-claims grounding
rule; a labeled roadmap is the one sanctioned place for forward-looking statements):
GUI internationalization; multi-language modeling content (localized entity
names/descriptions); SPDX 3.0 AI-BOM export alongside CycloneDX; SysML v2 support;
rework of the packaged agent skills. No separate roadmap docs page — one section,
kept short so it cannot drift into feature documentation. Quickstart
delta: add the optional guidance-import step (`arch-import-guidance` — guidance is
license-separated and absent until imported; today a fresh clone hits empty authoring
guidance with no README hint) and the optional assurance bootstrap
(`arch-assurance init && arch-assurance seed --with-signals`). Verify the "Java 11+"
prerequisite claim against the current runtime and document `ARCH_JAVA` in installation.

**Tier/facet story:** told once in `views-and-exploration.md` (browse-side) and once in
`git-sync-promotion.md` (workflow-side), cross-linked; not a separate page.

## 3. Screenshot plan (feeds E2 — capture itself stays restart-gated)

### 3.0 Media policy — the self-model's assurance content is public

ENG-ARCH-REPO's assurance content is the self-model of this open-source software: the
owner has declared it TLP:WHITE, and it **can and should be used in examples** — the
real STPA-Sec analysis and the real dogfooded SBOM are more honest showcase material
than any fixture. This supersedes the synthetic-only reading of the uplift plan's media
invariants for self-model content (that plan's invariant is amended accordingly). The
existing media harness's live self-model captures are therefore *aligned* with policy,
and `diagrams.md`'s "the figures are our own STPA-Sec analysis" claim stands.

What still holds:

1. **Scope boundary:** captures come only from the self-model store (the shipped
   `seed-assurance.json` content) — never from a store holding any non-self-model or
   above-WHITE data. The capture harness runs against a temp workspace seeded from the
   fixture seed, which is what makes captures deterministic AND provably self-model-only.
2. **Synthetic augmentation, marked:** where the live self-model lacks illustrative
   data (the active snapshots hold 0 findings post-remediation, so a 0-row findings view
   or an unstyled posture diagram teaches nothing), seed clearly synthetic findings and
   keep the visible "Synthetic documentation data" marker **on those shots only**. Never
   present invented vulnerabilities of real components as genuine.
3. **Determinism & provenance:** named deterministic tests, stable IDs (never "first
   result"), and the media provenance manifest stay as specified — their value is
   reproducibility, not confidentiality.
4. **Hygiene scan:** the denylist scan narrows to genuine secrets — credentials, private
   paths, tokens — not CVE identifiers or dependency versions, which are public facts of
   an OSS dependency tree.

Every shot: named deterministic test, stable IDs below, manifest entry per I-E3
(including the exact viewpoint parameter bindings — note the execute surface requires
`group` as a list, not a scalar), 1440×900 @2x unless noted. Assurance/security shots
(S7–S11, S13) use the seeded self-model store, with the synthetic marker only on
synthetically augmented data per rule 2.

| # | Shot | Surface | IDs / parameters | Why it earns the spot |
|---|---|---|---|---|
| S1 | Content-first nav: entities list + tier facet + workflow/status cluster + search | GUI entities list | filter: domain=application | Replaces `hero-overview.png`; proves the nav/tier story (I-E4 anchor shot) |
| S2 | Strategy overview | GUI diagram view | `ARC@1784483951.yBNaaU.strategy-overview` | Required by the E2 scope; home = showcase (strategy leg of the tour) |
| S3 | Value stream with stages | GUI diagram view | `ARC@1784483996.YRywG6.value-stream-deliver-an-architecture-aligned-change` | Home = showcase; shows stage decomposition + value delivery on the tour's strategy leg |
| S4 | Resource investment heat map | GUI diagram view | `ARC@1784488894.WwyJAa.resource-investment-map` | Required by the E2 scope; home = `viewpoints.md` styling worked example (`investment_level` heat-map rule) |
| S5 | C4 progression — **three separate image assets**, each with its own filename, alt text, stable assertion, and manifest record | GUI diagram views | `CSC@1780829783.z8RRON.amp-system-context`, `CC@1780829785.Z_fI-N.amp-containers`, `CC@1780829793.K3l46j.architecture-backend-components` | The self-model showcase spine: the platform describing its own runtime |
| S6 | Motivation-coverage table with one clearly passing and one clearly failing branch | GUI viewpoint execution | slug `motivation-coverage`, `gaps_only=true`, over a **dedicated fixture repo** (the live gap count drifts with the model; a two-branch fixture is deterministic and more instructive — cite the live self-model in prose as dogfooding evidence instead) | The honest-coverage flagship; pairs with `coverage-semantics.md` |
| S7 | Assurance graph-explore canvas | GUI assurance explorer | the real STPA-Sec analysis `STPA@1784721732.pflr.3e4395` (PlantUML Preprocessor Untrusted-Input Disclosure) from the seeded self-model store; route deep-link visible in the address bar | Explorability + deep-linkable node route, shown on a genuine dogfooded analysis |
| S8 | Security-posture viewpoint render + legend | GUI diagram view | slug `security-posture` over the seeded self-model store with synthetically augmented findings (marker visible per §3.0 rule 2 — the live snapshots hold 0 findings, which renders nothing worth showing) | Metrics-styled diagram + legend + classification banner |
| S9 | Entity detail: Service-specialization attributes + derived security-metrics panel | GUI entity detail | `APP@1777293133.OYEmP1` (Architecture Backend) with its real seeded snapshot (BOM counts are genuine; augmented findings marked if seeded) | Required by the E2 capture list verbatim; shows typed attributes and virtual attributes side by side |
| S10 | Locked/unavailable metrics state | Same surface as S9, store locked | fixture: locked store | The fail-closed story — "never stale or mixed values" needs to be *seen* |
| S11 | Stamped export example | Export artifact (may be cropped) | from S8's diagram — same fixture provenance, fail-closed assertions, and manifest entry as S8; the synthetic marker, stamp, and classification banner must remain visible after any crop | Proves the ephemeral/stamped export path |
| S12 | Guidance wizard with composed domain context | GUI entity-create form | type: application-component (ancestor context sections expanded) | Guidance v2's visible payoff; anchors the new guidance page |
| S13 | Guided method workflow (STPA wizard step or method-completion review) | GUI assurance workflow route | the real STPA-Sec self-model analysis (seeded store) | The one primary assurance *workflow* shot (S9/S10 both stay — the E2 capture list requires each); anchors the method-workflow guide (§1 row 2b) |

Dropped from the old suite: nothing removed blindly — existing media files stay until
their referencing page is reworked, then each is either regenerated under the harness or
deleted with its reference (no orphan images; link check enforces).

## 4. Wording & voice edits

- **W1 (README + docs/index):** the "screenshots throughout these docs are the tool
  describing itself" claim **stands** under the §3.0 policy — the assurance examples
  ARE the self-model. The only amendment: one sentence noting that illustrative
  security findings may be synthetically seeded and are then visibly marked, while
  users' own assurance content remains confidential by design.
- **W2 (README quickstart):** currently implies a fully working authoring experience
  after step 5; add the guidance-import caveat (see §2).
- **W3 (`04-assurance/index.md` + `methods.md`):** verify the supply-chain-signals
  wording reflects the refresh-run/active-snapshot model rather than one-shot ingest.
- **W4 (`01-motivation.md`):** no structural change; sweep for claims that predate
  strategy/upgrade/licensing capabilities ("outcomes we expect" section may now
  under-claim — several expected outcomes are shipped and demonstrable; point at the
  showcase instead of restating).
- **W5 (global sweeps at the end of E1):** (a) no *planning-vocabulary* references in
  persistent docs (hard rule) — precise patterns: `PLAN-`, `TASKS-`, `PROMPT-`,
  `WU-\d+`, `\bPhase [A-Z0-9]+\b` (implementation phases), `D\d+\b` decision IDs,
  "companion plan", and §-references *to plan documents*. Plain `§` is legitimate for
  standards citations (ArchiMate chapters, ISO codes) and intra-doc sections and must
  NOT be swept; generated MCP tables are excluded from the sweep (defects there are
  fixed at the tool-description source). (b) no "NEW/REVISED" changelog voice — docs
  state current truth only; (c) terminology: "assessed entity" (not "anchor") wherever
  security-signal attachment is user-facing, matching the live MCP surface;
  (d) "promote/promotion" only for tier transfer; (e) no internal-process voice in
  public docs — phrases like "flagged for review", "genuinely ambiguous cases",
  "will be reconciled" narrate the project's workflow instead of stating the
  adopter-facing contract; rewrite to what the reader can rely on.

### 4.1 Quality-review findings (Diátaxis, voice, consistency — surveyed 2026-07-22)

Method: pattern sweeps over every docs page + README (AI-overused vocabulary, antithesis
constructions, staccato fragments, question headings, spelling variants) and full prose
reads of the voice-defining pages (README, 01-motivation, 02-installation head,
03-modeling/index, 04-assurance/index, viewpoints.md head).

- **Q-1 — Spelling is mixed British/American, sometimes within one page**
  (03-modeling/index: title "Architecture Modeling", first line "Modelling aims").
  Counts: "modeling" 48 vs "modelling" 11; also organisation(5)/organization(3),
  initialise(4)/initialize(4), artefact(2), summarised(2). **Task:** standardize on
  American English everywhere ("artifact" already is); add the sweep to B5.
- **Q-2 — `01-motivation.md` mechanical defects:** several paragraphs unwrapped (single
  700+-char lines) against the page's own wrap style; trailing spaces; a spaced hyphen
  used as a dash ("guidance stalls autonomous teams … - as concurrent work increases");
  one genuine run-on ("Avoiding such risks and costs enables teams to take full
  advantage of the velocity enabled by agentic work while maintaining unity of effort
  leading to…"). **Task:** copy-edit pass in B4 (W4 absorbs this).
- **Q-3 — Cross-doc over-promise found:** `04-assurance/index.md`'s page table says
  Security signals covers "VEX", but `security-signals.md` has no VEX section. Resolved
  by the gap-#3 expansion; added to the B5 consistency checklist as the pattern to hunt
  (index summaries vs actual page contents, all four index pages).
- **Q-4 — `02-installation.md` internal inconsistency:** requirements table says
  Node 18 minimum while the Debian snippet installs Node 20 (`setup_20.x`); "Java 11"
  minimum needs re-verification against the current PlantUML jar and the `ARCH_JAVA`
  resolution order (which the page predates). **Task:** part of the B4 installation
  refresh.
- **Q-5 — Self-model deep-link convention** ("Open the diagram in a running app:
  http://localhost:8000/diagram?id=…") is used in 01-motivation and 04-assurance/index
  but not uniformly wherever self-model diagrams appear. **Task:** apply consistently
  (incl. the showcase); state the default-port assumption once.
- **Q-6 — AI-phrasing sweep: substantially clean.** No hits for the slop vocabulary
  (seamless/robust/leverage/delve/game-changing/…), no staccato fragment chains, no
  antithesis "This is not X. This is Y." constructions. "not just" appears 5×, two of
  them inside *generated* MCP tool-description tables — if worth fixing, fix in the
  tool-description source, never in generated output. One question heading (README "Is
  this for you?") — keep; it earns its place and fronts an honest is/isn't split. The
  one structural AI-flavored habit is **bold-lead bullet density** (01-motivation runs
  five consecutive sections of bold-lead lists): where it reads mechanical, vary the
  rhythm during W4 — but do not de-structure grounded driver/goal enumerations that
  mirror self-model entities.
- **Q-7 — Diátaxis verdicts by page type:** installation is a clean numbered how-to;
  the index pages are good signposted hubs; `viewpoints.md` is the house model — it
  *explicitly* splits explanation/how-to from the schema reference page in its opening
  lines. The genuine violations are the ones §1/§2 already handle: a design/explanation
  doc in user-docs space (gui-capability-design → `docs/architecture/`), a reference
  stub that is really a promise (rest-api), and a missing how-to (upgrade guide). No
  wholesale restructure warranted — confirms §2.
- **Q-8 — Audience gap: the Diátaxis *tutorial* quadrant is empty.** README audience
  explicitly includes people who "want to get into architecture modeling", but no page
  walks a first modeling session (quickstart ends at a running backend; the showcase is
  a *reading* tour of a finished model, not a *doing* tutorial). See Q4 in §6.

## 5. Execution plan (E1, after owner approval)

Batches ordered so verification pages land before pages that link to them; each batch
ends with a link-check pass. Media slots are committed as alt-texted placeholders
referencing manifest names (real images arrive in E2, restart-gated).

1. **B1 — Reference truth:** licensing (expand), rest-api (VERIFY), configuration
   (signal backends), MCP tables `--check`, docker-compose refresh, upgrade-guide (new;
   operational narrative **moved** out of cli-and-backend, which keeps syntax/flags/exit
   codes + a link), `docs/architecture/` cleanup (dependency-policy burn-down restated
   against the current baseline, glossary reconciliation note resolved — §1 row 20).
2. **B2 — Modeling:** viewpoints/impact/coverage VERIFY pass (incl. the strategy-viewpoint
   + heat-map worked-example mention in `viewpoints.md`), views-and-exploration
   (workflow/status cluster — explicit deliverable), projects-and-grouping +
   document-types touch-ups.
3. **B3 — Assurance & guidance:** exploring-assurance (new), method-workflow guide
   (§1 row 2b), security-signals expansion, guidance page (new) + ontology-modules
   slim-down **including updating the known inbound links to the extracted guidance
   section (`reference/configuration.md`, `reference/cli-and-backend.md`) in the same
   commit**, methods/index wording, `diagrams.md` refresh,
   gui-capability-design rewrite + relocation.
4. **B4 — Top level:** installation refresh (incl. Q-4 Node/Java reconciliation),
   README amendments, docs/index nav + audience entry paths, 01-motivation copy-edit
   (W4 + Q-2 + Q-6 rhythm), showcase (new; Q-5 deep-link convention),
   first-modeling tutorial (new; §6 Q4).
5. **B5 — Checks (verify-only; content fixes go back to the owning batch):**
   link check via a new `tools/check_doc_links.py` with a stated contract — relative
   file targets, Markdown heading anchors, orphan-media detection; external URLs
   behind an allowlist/offline-skip — wired into CI alongside the other doc gates;
   generated-reference check (`uv run tools/generate_mcp_docs.py --check` +
   `tools/generate_notices.py --check`); W5 grep sweeps; Q-1 American-English spelling
   sweep; Q-3-pattern consistency check (every index page's summaries vs the pages they
   describe); read-through at desktop and narrow widths.

Gates: docs-only commits still run the backend gates (cheap, catches doc-adjacent
tooling drift); each batch is one commit.

## 6. Open questions for the owner

(none currently)

Resolved (revisit only if the owner objects):

- **Q1 — `enterprise.git.url`:** the example enterprise repo **will be public**. The
  tracked default becomes its public **HTTPS** URL (SSH stays a documented option for
  writers); installation docs describe the fresh-clone experience against it. Note the
  workspace resolver rejects a contentless `local:` path, so the public-remote default
  is also the only documentation-truthful option without product changes.
- **Q5 — public repository identity:** confirmed **`mbauer83/architectonic`**. The
  project moves there with a **clean history**, with all PLAN/TASKS/PROMPT files, PDFs,
  and stray files removed. Publication gate (before the move): finish the remaining
  workstreams AND a clean CI run, verified via the GitHub CLI (`gh run list` /
  `gh run watch` on the final commit). The release-readiness check verifies together:
  repo name, badges, clone URL, package name, the self-model's source-repository
  attributes, and the enterprise-repo URL — plus a sweep that no doc references the
  removed planning files (W5 covers the vocabulary; this covers literal file links).

- **Q2 — showcase placement:** standalone `docs/06-showcase.md`, linked from the README
  (too long and structurally rich for the README; standalone preserves stable deep
  links and the public/synthetic boundary).
- **Q3 — S6 stability:** dedicated fixture repo with one passing and one failing branch
  (deterministic and more instructive); the live self-model is cited in prose as
  dogfooding evidence. Folded into §3 S6.
- **Q4 — first-modeling tutorial:** added. Grounded in the self-model's own value
  stream `VS@1784483104.lVJLuL` (Model the First Engagement): the tutorial's success
  criterion is the stream's exit condition — the first model answers a real question —
  not "files were created". One page, generic, no per-domain content; lands in B4.

## 7. In-app documentation serving (evaluated: recommended, as a follow-on workstream)

**Idea:** the backend serves the documentation for browser viewing, and each GUI
application area carries a "Docs"-labelled link to its most relevant section.

**Verdict: worth doing.** It fits the product's self-contained deployment story (the
Docker image would carry its own manual, readable offline), it matches the
self-describing ethos, and contextual help is the cheapest way to make the deeper
capabilities (viewpoints, assurance methods, promotion) discoverable from where users
actually encounter them. The enabling facts are already in place:

- The GUI already ships `marked` behind `MarkdownService.renderMarkdown` (used by the
  document viewer), so a docs viewer is a thin new view over existing machinery — ship
  `docs/**/*.md` + `docs/media/` as static assets and render client-side in an SPA
  route with a small table of contents.
- **Route naming constraint:** FastAPI already owns `/docs` (Swagger UI) and `/redoc`.
  The in-app manual lives at **`/help/...`** in the SPA router; nav label "Docs" is
  fine, but the literal `/docs` path must stay Swagger's.

**Design sketch (one bounded workstream, after E1 content stabilizes):**

1. Build step copies `docs/` into the GUI dist (or the backend mounts it as static
   files); no server-side rendering, no runtime markdown pipeline in Python.
2. `HelpView` at `/help/:page*` renders the markdown, rewrites relative links
   (`docs/a/b.md` → `/help/a/b`, media → the static mount) and degrades gracefully for
   repo-only targets (links into `engagements/`, `LICENSE`, …) by pointing at the
   public repository.
3. A typed **help-link registry** maps each application area to a docs page + anchor
   (entities/list → modeling views page; viewpoint views → viewpoints page; assurance
   areas → the method-workflow and exploring pages; settings/sync → configuration and
   git-sync pages). View headers render the "Docs" link from the registry.
4. The `tools/check_doc_links.py` contract (§5 B5) grows one more check: every registry
   target resolves to an existing page + anchor — so GUI help links cannot rot silently.

**Sequencing:** docs content first (E1), then this workstream, then E2 — screenshots
then show the finished chrome. It is a product change (frontend + possibly a static
mount), so it runs under the normal code gates, not as part of a docs batch; owner
starts it explicitly.
