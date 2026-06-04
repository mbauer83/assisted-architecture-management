# PLAN — Assurance Capability: STPA / CAST / GRC

> **Status — Phase 3 complete (2026-06-05). Phase 4 is next.**
> **All design decisions are locked** (§18 — no open items remain). **Canonical progress tracker = §24**
> (phased checklist + per-phase Definitions of Done + status). When you pick this up: update the §24 tracker
> and check `[x]` items as they complete; detailed specs (full `entities.yaml`, JSON schemas, port interfaces)
> move to `plans/assurance-overlay/` as each phase begins.
>
> Tag legend: **[RESOLVED]** decided · **[CONFIRM]** recommended, awaiting your sign-off · **[OPEN]** needs
> research/discussion. Last updated: 2026-06-04.

## 1. Purpose & scope

Add **safety, security, and governance/risk/compliance (GRC)** analysis to the platform
as a **first-class, reusable capability** — not bolted onto the ArchiMate/SysML model, but a
**separate module family** that *cross-references* the architecture model. Cover the whole
spectrum with a small, coherent surface:

- **STPA / STPA-Sec** — proactive systems-theoretic hazard *and* security analysis.
- **CAST** — reactive accident/incident causal analysis on the same control-structure model.
- **GRC** — governance (accountability over the control structure), risk (ISO 31000 lifecycle),
  compliance (obligations → controls → evidence → audit).

Modeling/dogfooding the system's own posture comes *afterwards* (separate effort), so this plan
is about the **capability**, optimised for users who are **not** experts in these methods or in
the relevant legal/standards landscape (see §15 — guidance-first design is a first-class requirement).

**Business context & drivers.** Three forces make this timely: (1) **regulation** — the EU AI Act phases in
(most provisions **2 Aug 2026**; high-risk *product* obligations under Art. 6(1) from **2 Aug 2027**): Art. 12
requires logging *capability*, **Art. 19/26** a **≥6-month** log-retention minimum, **Art. 18** a **10-year**
technical-documentation retention; the EU **Cyber Resilience Act** adds vulnerability **reporting** (11 Sep 2026)
and **SBOM + secure-by-design** obligations (11 Dec 2027), reaching even SMEs *(profiles are framework/
jurisdiction-scoped, not legal advice)*; (2) **audience** — personal
projects and small/medium teams who lack dedicated safety/GRC/security tooling and method expertise, so the
capability must be turnkey and guidance-first; (3) **differentiation** — STPA/MBSE and GRC tools leave a
usability×interoperability gap (no single tool is both genuinely usable *and* model-integrated). **Value:**
assurance over the *same live, traceable architecture model* — the loss → hazard → control → evidence → record
chain is one queryable graph, not disconnected documents.

### 1.1 Goals, non-goals, success criteria
**Goals**
- **G1** STPA, CAST, GRC as first-class, reusable capabilities (not bolted onto the model).
- **G2** One traceable graph: assurance↔architecture links are **navigable bidirectionally but persisted
  one-way** (every confidential edge is stored on the assurance side; architecture repos hold none) (§6).
- **G3** Safety is never subordinate to risk — enforced, not advisory (§2.1).
- **G4** Usable by non-experts: guidance-first method + legal/standards coaching (§15).
- **G5** Keep the architecture-modeling surface uncluttered — separate module family + MCP server.
- **G6** Assurance analysis *improves* the architecture model: unmodeled structure becomes a visible
  modeling signal (§7.1).

**Non-goals**
- Not a replacement for dedicated certification/safety-case submission tools.
- Not auto-generating compliance verdicts or legal advice (we assist; humans decide).
- Not a quantitative probabilistic-risk engine (FTA/FMEA numerics) in Phases 1–2.
- Not self-applying to ENG-ARCH-REPO yet (separate, later effort — Phase 7).

**Capability success criteria** (see §22 for per-story acceptance criteria)
- A non-expert can complete a basic STPA end-to-end via the skill/tools, producing a verifiable,
  traceable analysis.
- A safety/security constraint cannot be silently closed by a low risk score.
- Threat/vulnerability catalogs can be updated **without code or ontology changes** (§4.1).
- Assurance artifacts never appear in / pollute the ArchiMate/SysML model views.

## 2. Conceptual foundation (agreed)

The three concerns are **not parallel silos and not "two lenses on a backbone."** They are
**nested layers of one control-theoretic stack**, unified by a single primitive:

> **The constraint, enforced through a hierarchical control structure.**

STAMP's most basic concept is the *constraint*, not the failure/event; losses arise when the
control structure fails to enforce the necessary constraints ([Leveson, *A New Accident Model*](http://sunnyday.mit.edu/accidents/safetyscience-single.pdf)).
That is also the GRC primitive: a *control* is a constraint; a *compliance obligation* is an
externally-imposed constraint plus a demand for evidence; *governance* is the assignment of
authority/accountability for who enforces which constraints — i.e. **the upper levels of STAMP's
socio-technical control structure** (regulators → management → operators → process).

- **STPA/STPA-Sec** = the *generator* (Losses → Hazards/Threats → Unsafe/Unsecure Control Actions →
  Loss Scenarios → derived **Constraints**).
- **CAST** = the *reactive generator* over the same model (Accident/Incident → control-structure-as-existed →
  flawed/observed control actions → causal scenarios → **corrective constraints**).
- **GRC** = the *lifecycle manager* around those constraints: governs (accountability), evaluates
  (risk), treats, and evidences (compliance).

### 2.1 The safety-subordination safeguard (non-negotiable)

Making "Risk" the root concept would silently reduce safety to *tolerable financial exposure* —
the exact probabilistic worldview STAMP rejects. Therefore:

- The neutral superset is **Assurance**, *not* Risk. Risk management is **one disposition discipline
  within** assurance, never its governing root.
- **A safety constraint is valid and must be enforced independent of any risk object.** A `risk`
  entity (§9) prices/prioritises; it can never be a precondition for a safety constraint's existence
  or a means to "close" it.
- **Disposition vocabulary is concern-class-typed** and **enforced by the verifier** (§16):
  - `concern_class ∈ {safety, security}` → `eliminated | prevented-by-design | controlled-with-evidence | alarp-justified`. **`accepted` is rejected** unless a justification document *and* an accountable sign-off connection are present.
  - `concern_class ∈ {operational, financial, …}` → classical `accept | mitigate | transfer | avoid` allowed.

## 3. Architectural decision: a separate "assurance" module family

**[RESOLVED]** Assurance artifacts are **not** ArchiMate/SysML model entities and do **not**
live under `model/<archimate-domain>/`. They form their own module family, persisted in their own
subtree — in a **separate, optionally-encrypted third repository** (the *confidential assurance tier*)
that gates the whole capability — cross-linked to the architecture model. The confidentiality
architecture is recorded in **ADR-001** (§26); §3.3 summarises the tier.

### 3.1 `module_class` on modules
Introduce a declared **`module_class`** (a.k.a. module family) on ontology modules **and** diagram-type
modules:

- `architecture` — `archimate_next`, `sysml_v2_min`, the ArchiMate/C4/sequence/activity diagram types.
- `assurance` — the new STPA/CAST/GRC ontology module and its diagram types.

Generic components (frontend navigation, MCP server scoping, persistence routing, verification
grouping) **branch on the declared `module_class`, never on hardcoded module names** (honours the
modularity-boundary principle: no domain logic in generic components). This lets the frontend treat
the assurance family distinctly — its own navigation area, its own affordances, its own "create"
flows — and integrate it in an optimised manner rather than interleaving it with model browsing.

### 3.2 Grouping axis + logical record layout
Assurance artifacts form a **fourth artifact family** with its own grouping axis (**analysis-collection**) —
analogous to the model-project / diagram-collection / document-collection axes, but **persisted in the
`ConfidentialAssuranceStore` (SQLCipher default), not in git** (§3.3, ADR-001 §26). The live source of truth is
the store; the tree below is the **logical record layout** the **export / private-git adapter** materialises
(and a useful mental model) — **not** the default persistence path:

```
(export / private-git adapter layout — NOT the default store)
assurance/
  analyses/<analysis-slug>/   ← one STPA or CAST analysis, or a GRC scope (losses/hazards/control-actions/ucas/…)
  registers/                  ← cross-analysis GRC views (risk register, control library)
```

- This **corrects** the earlier "model-project group" idea — assurance analyses are *not* ArchiMate
  model-projects. They are their own family with their own grouping axis, in their own confidential store.
- Cross-references to architecture model entities are **typed connections** (§6) and obey a **strict
  asymmetric-reference invariant: references flow `assurance → {engagement, enterprise}` only, never the
  reverse.** A non-confidential artifact must never embed a link that reveals a confidential finding's
  existence or content (extends the existing enterprise↛engagement rule). The §7.1 "model this" workflow
  stays consistent: the binding lives on the assurance side; the created architecture entity carries no
  sensitive framing.

### 3.3 Confidential assurance store (pluggable) — see ADR-001 (§26)
The assurance graph lives in a **separate, confidential store** (its own subtree/DB, distinct from
engagement/enterprise), accessed via a pluggable **`ConfidentialAssuranceStore` port**:
- **Pluggable backend (convenience-first default):** **SQLCipher** embedded + encrypted, key
  **auto-managed in the OS keychain** = zero-ceremony default (personal/SMB); **PocketBase** (RBAC + API)
  for teams; **Supabase/Postgres** and **private-git** as advanced/opt-in. The backend builds the
  **in-memory read model** from whichever adapter (SQLite index is `mode=memory`/ephemeral — confirmed).
- **Capability gating (fail-closed, off-by-default):** assurance MCP servers + GUI features **do not exist**
  unless a store is configured *and unlocked*; configured-but-locked shows a locked banner
  (mirrors `--read-only`/`--admin-mode`); enabling is a **guided one-command flow**, not a config chore.
- **Immutable records from day one (EU AI Act):** a separate **`AssuranceArchive` port** holds an
  append-only, hash-chained audit log + sealable signed baselines (§26 ¶6). Live store ≠ archive.
- **One-way references** `assurance → architecture` (ID-only); git holds no confidential pointers.
- **What storage does *not* cover:** content decrypted for an authorised session still flows to an LLM via
  MCP — that vector is owned by TLP classification + MCP max-classification (§23), never by at-rest
  encryption. Complementary layers, different vectors.

### 3.4 UI boundary (Phase-0 decision — detail in §30)
Assurance is a **separate UI experience on shared engines**, *not* the architecture-authoring chrome: reuse the
rendering/data engines (graph, diagram, matrix, read-model, SSE) + the design system, but **do not** reuse the
ArchiMate entity form / connection picker / domain browse for assurance authoring — STPA/CAST/GRC are
workflow-driven, not artifact-driven. Bespoke surfaces (method wizards, control-structure canvas, risk register)
are driven declaratively by `module_class`; generic components carry no assurance branches. Stated here (not just
§30) because it is a **Phase-0 decision**: it shapes module boundaries, frontend routing, and test strategy.

## 4. Unified artifact ontology (one module: `src/ontologies/assurance/`, `module_class: assurance`)

New **entity types** (the concepts ArchiMate genuinely lacks). Shared across STPA/CAST/GRC where the
semantics are identical; discriminated by properties rather than duplicated types.

| Type | Prefix | Used by | Notes |
|---|---|---|---|
| `loss` | LOS | STPA, CAST, GRC | Unacceptable, stakeholder-relevant outcome. |
| `hazard` | HAZ | STPA(safety), STPA-Sec(security) | **Generic**; `concern_class` ∈ {safety, security, privacy, …} selects the lens. **No distinct `threat`/`vulnerability` types** — in STAMP a *vulnerable system state* is the security analog of a hazard; threat/vuln **classification** is pluggable reference data (§4.1). **[RESOLVED]** |
| `control-structure-node` | CSN | all | Controller / controlled-process / actuator / sensor *within the assurance model*; **optionally binds** to an architecture entity (§7). `node_role` + `binding_status`. |
| `control-action` | CTA | STPA, CAST | A specific action a controller can issue — the unit STPA analyses. `controller →issues→ it →acts-on→ controlled-process`; bindable to an architecture behaviour/flow; gives every UCA a stable `control_action_id`. |
| `unsafe-control-action` | UCA | STPA, CAST | References **one `control-action`** (mandatory) + its controller. `uca_type` ∈ {not-provided, provided, wrong-timing (too-early/late/out-of-order), **stopped-too-soon-or-applied-too-long**}; plus `context` (context variables/conditions), `timing/duration applicability`, `parameter conditions`; `concern_class`; **`mode` = hypothesized (STPA) \| observed (CAST)** (§10). Traces `violates → hazard`. |
| `loss-scenario` | LSC | STPA, CAST | Causal scenario; CAST scenarios are `mode=observed`. |
| `assurance-constraint` | ACN | all | The pivot (§8). `concern_class`, `level` (system/controller/technical), `disposition`. Separate from ArchiMate `requirement`; **`refines`/`satisfied-by`** one — implementation is the requirement's ArchiMate `realized-by` (no `enforced-by`). |
| `risk` | RSK | GRC | First-class, owned (§9). Evaluates a hazard/loss-scenario; treated-by constraints. |
| `incident` / `accident` | INC | CAST | An actual occurred loss event under investigation. |
| `corrective-action` | CRA | CAST, GRC | Recommendation from an investigation or audit; may yield new constraints. |
| `obligation` (+ `obligation-clause`) | OBL | GRC | A **confidential** compliance obligation instance (does *our* system comply?), optionally `cites` a **public framework catalog** entry (`scheme:code`, e.g. `ISO26262:6-8`; reference-vocab §4.1). Status/evidence are assurance-owned — **never stored in architecture motivation**. |

New **connection types** (the joins; all **stored assurance-side** — §6 one-way persistence rule):
- control loops: `issues` (controller→control-action), `acts-on` (control-action→controlled-process), `feedback` (process→controller);
- STPA chain: `concerns` (uca→**control-action**, mandatory) + `by-controller` (uca→controller); `violates` (uca→hazard); `leads-to` (hazard→loss); `explains` (loss-scenario→uca); `derives` (loss-scenario/incident→assurance-constraint);
- refinement & governance (assurance-side): `refines` / `satisfied-by` (assurance-constraint→architecture `requirement`); `accountable-to` / `responsible-of` (constraint/node→role — RACI); `evidenced-by` (assurance-constraint→artifact/document) — *implementation reuses the requirement's ArchiMate `realized-by`; no separate `enforced-by`*;
- GRC: `assesses` (risk→hazard/loss-scenario), `treated-by` (risk→assurance-constraint), `complies-with` (assurance-constraint→obligation), `cites` (obligation→public catalog `scheme:code`);
- linkage: `binds-to` (control-structure-node/control-action→architecture element), `investigates` (incident→control-structure/hazard).

**Cross-module wiring [RESOLVED]:** extend the loader to support **module-scoped class wildcards**
`@<module>:<class>` (e.g. `[control-structure-node, "@archimate_next:structure-element", [binds-to]]`) — *not*
bare `@class` against the global merge. Literals stay valid where a fixed set is meant (`requirement`, the few
structural binding targets). This is a **generic registry capability** (no domain logic). Mitigations that keep
it from drifting (the reason to scope rather than use bare `@class`):
- **Scoped to a named module** → no cross-module class-name collisions; the target set is independent of which
  *other* modules are loaded.
- **Resolved + frozen at registration** into the concrete type set, and **surfaced through the existing
  ontology-inspection surface** (the `diagram_types`/registry REST routers exposing `effective_entity_types`/
  `effective_connection_types`, and `artifact_authoring_guidance`) — *no new inspection endpoint needed*.
- **Startup-validated, fail-closed:** an unresolvable/empty `@module:class` is a startup error (extends the
  existing startup-validation), not a silently-empty rule.
- Residual behaviour ("a newly-added type in the *same named ontology* auto-joins") is the *intended* meaning of
  the wildcard, now explicit and inspectable. Lands with the §29 module-mechanism work (Phase 0).

### 4.1 Pluggable, versioned threat/vulnerability reference vocabulary **[RESOLVED]**
Threat/vulnerability taxonomies must be **data, not schema**. Rationale: STPA-Sec deliberately
**avoids enumerating threats** and treats the *vulnerable system state* as the security analog of a
hazard, focusing on controlling vulnerabilities ([STPA-Sec, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7959614/));
and STRIDE/ATT&CK/CAPEC/CWE/CVE are **continuously-evolving reference catalogs** built to interoperate,
not fixed models ([ATT&CK/CAPEC mapping](https://www.nopsec.com/blog/mapping-cves-and-attck-framework-ttps-an-empirical-approach/)).
Ontological analysis likewise treats vulnerability as a *dispositional aspect*, not a class
([Oliveira/Sales/Guizzardi, COVER](https://link.springer.com/chapter/10.1007/978-3-031-21488-2_6)).

Design:
- A generic `classification` mechanism on `hazard`/`loss-scenario`: a `(scheme, code)` pair
  (e.g. `STRIDE:Tampering`, `CWE:CWE-89`, `ATT&CK:T1059`, `CVE:CVE-2026-…`), validated against a
  **versioned reference-vocabulary file** loaded as data (e.g. `.arch-repo/reference/<scheme>.<version>.yaml`).
- STRIDE attaches at the **loss-scenario** step (per the STPA+STRIDE literature); external catalog
  IDs are validated, vocabulary-backed where available, free-form otherwise.
- **New/updated catalogs ship as data updates — never code or ontology changes** (satisfies G + your
  evolving-set concern).
- Keep `concern_class` (the analytical lens) strictly distinct from `classification` (the catalog tag).
- Any external adversary/threat-source the user wants to record is a *classification*, not a structural
  entity type.

## 5. Bindings to the architecture model
`control-structure-node` (and optionally `assurance-constraint`) may **bind** to an architecture
entity using the existing meta-ontology binding system (the same mechanism C4 uses to map its
diagram-owned entities transparently to ArchiMate entities). Binding is **optional traceability**,
not a prerequisite (§7).

## 6. Persistence & connection design (precise)

Single source of truth = the assurance knowledge graph (assurance entities + typed connections), held in the
**`ConfidentialAssuranceStore` (SQLCipher default, §3.3 / ADR-001)** — *not* git files. In the table the
**"Where"** column gives the **logical record location** (the path the export / private-git adapter would use);
the live store persists these as records. Properties are validated by the module attribute-profiles (§29.1).
Documents and diagrams are **views/narratives that reference the graph, never duplicate it.**

**Cross-link persistence rule (one-way): bidirectional *navigation*, one-way *persistence*.** Every confidential
edge — *including* those whose semantic predicate reads architecture→assurance (e.g. a control measure *enforces*
a constraint) — is **stored in the assurance store** (as the assurance-side reverse edge); architecture repos
hold **no** pointers into assurance. Back-references shown on architecture views are **computed** in the
read-model for unlocked sessions, never persisted. This preserves the §3.2 confidentiality invariant.

| Artifact | Persisted as | Where | Key connections |
|---|---|---|---|
| Loss | entity `loss` | `assurance/analyses/<slug>/losses/` | `hazard→leads-to→loss`; `loss→association→stakeholder/value` (architecture) |
| Hazard / Threat scenario | entity `hazard` (+`concern_class`) | `…/hazards/` | `→leads-to→loss`; `→at-asset→` architecture element |
| Control-structure node | entity `control-structure-node` | `…/nodes/` | control loops via `control-action`s (`issues`/`acts-on`/`feedback`); `binds-to→` architecture element (optional) |
| Control action | entity `control-action` | `…/control-actions/` | `controller →issues→ it →acts-on→ controlled-process`; `binds-to→` architecture behaviour/flow; referenced by every UCA (`concerns`, mandatory) |
| UCA | entity `unsafe-control-action` | `…/ucas/` | `→concerns→` **one `control-action`** (mandatory) + `→by-controller→` controller; `→violates→hazard`; props: `uca_type`/`context`/`timing`/`parameter`/`mode` |
| Loss scenario | entity `loss-scenario` | `…/scenarios/` | `→explains→uca`; `→derives→assurance-constraint` |
| Assurance constraint | entity `assurance-constraint` | `…/constraints/` | (all edges **stored assurance-side**) `→refines/satisfied-by→` architecture `requirement` (implementation via *its* `realized-by`); `←derives←` scenario/incident; `→complies-with→` obligation; `→evidenced-by→` doc/artifact; `→accountable-to→` role |
| Control measure (implemented control) | **an existing architecture element** realizing the requirement the constraint refines — *no new relation* | architecture model | reached via `constraint →refines→ requirement →realized-by→ element` (ArchiMate `realization`, reused) |
| Governance / accountability | connection `accountable-to` / `responsible-of` **stored assurance-side** (constraint/node → role) | assurance store | reuses architecture `role`/`business-actor` as owners (RACI); architecture holds no back-pointer |
| Risk | entity `risk` (§9) | `…/risks/` or `assurance/registers/` | `→assesses→hazard/loss-scenario`; `→treated-by→assurance-constraint`; `owner` connection |
| Obligation / compliance | **assurance-owned** entity `obligation` (+ `obligation-clause`); the framework *catalog* is public reference data (§4.1) | `…/obligations/` (store) | `constraint →complies-with→ obligation`; `obligation →cites→ <catalog scheme:code>`; status/evidence assurance-side (never in architecture motivation) |
| Evidence | reuse `artifact` or a document | technology / docs | `constraint→evidenced-by→` |
| Incident / Accident (CAST) | entity `incident` | `assurance/analyses/<cast-slug>/` | `→investigates→` control structure; `→leads-to→loss` |
| Corrective action | entity `corrective-action` | `…/` | `→derives→assurance-constraint` |
| STPA/CAST/risk/compliance narratives | **document types** (§13) | `docs/assurance/<slug>/` | E155 forces links to the entities above |
| Control-structure / UCA matrix / risk matrix / bowtie / GSN | **assurance diagram types** (§12) | `assurance/…/` diagram catalog | views over the graph |

**Circumspection / edge cases baked into the design:**
- **Promotion:** an assurance entity must promote *with* its connections; **block promoting a
  `safety`/`security` constraint lacking an accountable owner or evidence** (else the enterprise
  inherits an orphan control). Promotion pre-check.
- **Cross-repo:** assurance analyses are usually engagement-local but reference enterprise assets —
  allowed by asymmetric references.
- **Unmodeled / wrong-granularity references:** see §7.

## 7. Control structure as a first-class assurance artifact (granularity handling)

**[RESOLVED]** The control structure is **owned by the assurance module**, not merely a
view over ArchiMate entities. Each `control-structure-node` carries a **`binding_status`**:

- `bound` — linked to an architecture entity (full traceability).
- `unbound-pending` — should be modeled in the architecture later (gap surfaced as *informational*).
- `out-of-scope` — deliberately finer-grained than the architecture model's decided scope; will not
  be modeled there. A free-text `granularity_note` records why.

This directly answers the reality that UCAs — **especially those found via CAST after an incident** —
often reference controllers/processes/aspects that are **not yet modeled or genuinely below the
architecture's chosen granularity**. The analysis is **never blocked** by model gaps; the verifier
*reports* unbound nodes rather than erroring. STPA's iterative refinement across abstraction levels is
supported by allowing nodes/UCAs at any level with later optional binding. **Control actions are first-class
`control-action` entities** on the loops (`controller →issues→ action →acts-on→ process`), giving every UCA a
stable referent (§4) rather than pointing at an anonymous connection.

### 7.1 Unmodeled structure as a modeling signal (bidirectional value) **[RESOLVED]**
When a UCA, loss-scenario, or `control-structure-node` cannot be tied to a definite architecture
entity/connection (`binding_status ∈ {unbound-pending, out-of-scope}`), that is itself a **signal that
the structure or activity may be worth modeling** in the architecture. This turns assurance analysis
into a *driver for model completeness* — realising G6 and the platform's humans-and-AI co-modeling goal.

- **Detect** — verifier/coverage emits `modeling-gap` findings: each lists the unbound assurance
  node(s) and the analysis that needs them.
- **Display** — unbound nodes render distinctly in the control-structure diagram (dashed/ghosted +
  gap badge); analysis and entity views show a "modeling gap" indicator; a **"Suggested model
  entities"** notice (mirroring the existing E155 suggested-link notices) prompts the author.
- **Act** — a guided **"model this"** workflow creates the corresponding architecture entity (correct
  type chosen via authoring guidance) and **binds** the assurance node to it in one step
  (`binding_status → bound`). Available to humans (GUI) and agents (assurance MCP tool).
- **Respect scope** — `out-of-scope` nodes are acknowledged once (with `granularity_note`) and excluded
  from repeated gap-nagging. The design deliberately distinguishes *"not modeled yet"* (act on it) from
  *"deliberately finer than the chosen scope"* (acknowledge and move on).

## 8. Assurance constraints: separate class + traceability **[RESOLVED]**

Create a **distinct `assurance-constraint`** type in the assurance module (do **not** reuse ArchiMate
`requirement`). Rationale: (a) ISO 26262 practice manages safety requirements as a *distinct, traceable*
class — Safety Goal → Functional Safety Req → Technical Safety Req — bidirectionally linked to functional
requirements, not merged ([BTC types](https://www.btc-embedded.com/iso-26262-requirement-types/),
[Ketryx](https://www.ketryx.com/blog/navigating-iso-26262-and-iec-61508-3-functional-safety-standards));
(b) the module-family separation (§3) keeps the architecture model pure. The constraint carries the **safeguard**
(`concern_class`, `disposition`, integrity/ASIL); the **functional/technical statement + its implementation stay
in ArchiMate** — so we do **not** duplicate requirements. The single assurance→architecture link is
`assurance-constraint →refines / satisfied-by→ requirement` (stored assurance-side); **implementation reuses the
requirement's existing ArchiMate `realized-by`** edges to components/processes/functions (those *are* the control
measures) — there is **no separate `enforced-by`**, which would just duplicate
`constraint →refines→ requirement →realized-by→ element`. The `level` property captures system-/controller-/
technical-constraint tiers; where a constraint's statement can't safely be made public, model a
functionally-phrased requirement (per the architecture principle) or accept no architecture link.

## 9. Risk: first-class **optional** entity **[RESOLVED]**, reconciled with the safeguard

GRC tooling treats risk as a **first-class, owned, dynamic object** linked to controls/obligations/
incidents — "but the register should not become a control inventory"
([Cerrix](https://www.cerrix.com/en/insights/blog/what-is-a-risk-register-and-how-do-you-create-one),
[ThinkCloudly](https://thinkcloudly.com/blog/risk-register-aligned-with-iso-31000/)). So:

- `risk` is an **optional** entity (the GRC evaluation overlay — *not* required for a hazard/constraint to be
  valid) with `likelihood`, `impact`, `risk_score`, `treatment`, `residual_*`, `review_date`, an **owner**
  (`accountable-to` connection), and `→assesses→` a hazard/loss-scenario, `→treated-by→` constraints.
- **Reconciliation with §2.1:** the hazard/loss-scenario/constraint chain exists and is enforced
  *independent of* any `risk` entity. Risk **references** that chain to prioritise/treat; it is never
  the chain's parent and never a means to close a safety constraint. The verifier forbids a `risk`
  with `treatment=accept` from being the sole disposition of a `safety` hazard.
- The **risk register** and **control library** are *query/matrix views* over `risk`/`constraint`
  entities, not separate stores.

## 10. CAST integration **[RESOLVED — full method, Phase 3, on the shared model]**

CAST is the **reactive** counterpart of STPA on the **same** STAMP control-structure model
([UL: STAMP/STPA/CAST](https://www.ul.com/sis/blog/introduction-to-stamp-stpa-and-cast),
[STPA/CAST handbook](https://www.flighttestsafety.org/images/STPA_Handbook.pdf)). It reuses ~90% of the
ontology and adds: `incident`/`accident`, `corrective-action`, and an **`observed` mode** on UCAs and
loss-scenarios. A CAST investigation reconstructs the control-structure-as-existed, identifies the
control flaws that occurred, and produces corrective constraints — which then flow into the same GRC
lifecycle. CAST and STPA are **distinct skills/workflows** over a **shared model** (§14).

**Temporal baseline (required for CAST).** CAST reconstructs the control structure *as it existed at the
incident* — so `mode=observed` alone is insufficient. Each investigation requires a sealed **`analysis_baseline`**:
`occurred_at` (incident time), `architecture_revision` + `assurance_revision` (the model state then), and a
snapshot/seal reference into the `AssuranceArchive` (§26). The baseline pins what "as-existed" means and makes
the investigation reproducible and audit-defensible (and is checked by `cast-complete`, §17).

## 12. Assurance diagram-type modules (`module_class: assurance`)
- **`control-structure`** — the core artifact; renders `control-structure-node`s + `control-action`s and their
  `issues`/`acts-on`/`feedback` loops; shows `binding_status` visually.
- **Matrices — split by fit [RESOLVED]:** the generic `matrix` type is an **entity×entity relationship matrix**
  (cells = connection-type abbreviations, rendered as a markdown table; confirmed in `src/diagram_types/matrix/`
  + `CreateMatrixView`). So: **reuse it for the traceability matrix** (constraint ↔ requirement ↔ hazard — an
  exact relationship-matrix fit); build the **UCA grid** (control-action × guideword) and the **risk heatmap**
  (likelihood × impact, coloured) as **bespoke assurance surfaces** (reusing the table/grid *rendering primitive*,
  not the relationship-matrix semantics). **Do not add heatmap/guideword logic to the generic matrix renderer** —
  that would put domain semantics in a generic component (modularity-boundary). Consistent with §30 ¶3 / §30.2.
- **bowtie** (threat→event→consequence with barriers) — Phase 6.
- **assurance-case / GSN** (claim→subgoal→evidence) — Phase 6; binds to losses/hazards/constraints/evidence.

## 13. Document types (narrative + audit records; E154/E155 enforce structure & links)
- `stpa-analysis`, `cast-investigation`, `risk-assessment`, `risk-treatment-plan`,
  `compliance-statement`, (`assurance-case` if not a diagram). Each ships as a default doc-type with
  required sections and required entity links so non-experts get a correct skeleton and traceability is
  enforced.

## 14. Skills — narrow set, designed holistically, built progressively **[RESOLVED]**

Four skills (one clean activity each; STPA-Sec is *inside* `stpa-analysis`, not its own). All author **only** via
the assurance MCP tools, over the shared model. **Skills are directories, not just `SKILL.md`** (per
[Anthropic's skills guidance](https://claude.com/blog/lessons-from-building-claude-code-how-we-use-skills)):
progressive disclosure via `references/`, `assets/` (templates), `scripts/` (executable helpers so the agent
*composes*, not rebuilds), `examples/` (worked cases), and a high-signal **Gotchas** section in `SKILL.md`. The
*full* design is planned now (so advanced capabilities aren't neglected); it is *implemented progressively*.

| Skill (trigger) | references/ | assets/ | scripts/ (advanced) | examples/ | Phase |
|---|---|---|---|---|---|
| **`stpa-analysis`** (proactive; STPA-Sec via `concern_class`) | STPA handbook; HARA/TARA (26262/21434); UCA guideword guide; reference-vocab | analysis-doc; control-structure scaffold; UCA-matrix; constraint | scaffold collection; UCA-matrix gen; run `stpa-basic-complete`; modeling-gap surfacing | worked STPA | 2 |
| **`cast-investigation`** (reactive; refs `stpa-analysis`) | CAST handbook; baseline/seal; CAST↔STPA | cast-doc; baseline; corrective-action | **seal baseline**; `cast-complete`; as-existed diff | worked CAST | 3 |
| **`grc-management`** (risk/treat/comply) | ISO 31000; 27001/NIST controls; obligation catalogs; SBOM/CVE/VEX (→§27) | risk-assessment; risk-matrix; treatment-plan; compliance-statement; coverage-dashboard | register/coverage views; `grc-control-coverage-complete`; seed obligation catalogs; SBOM/CVE-context pull (P5) | worked risk+compliance | 3 (P5 scripts) |
| **`assurance-case`** (consumes the three) | GSN; assurance-case patterns; STPA→GSN | GSN argument; case-doc | draft GSN from hazards→constraints→evidence; argument-completeness check | worked GSN case | 6 |

**Cross-skill references:** `cast-investigation`→`stpa-analysis` (shared control-structure method);
`assurance-case`→all three; all→`archimate-modelling` (the "model this" gap workflow + binding).

**Ask, don't assume (skill behaviour rule).** Where a step needs information that **cannot be read or inferred
with very high confidence** from the available sources (model, store, repo, attached docs), the skill must
**ask the user, or point to the source it needs**, rather than tacitly assume — *especially* for
safety/security/legal judgements (losses, severity, integrity/ASIL, acceptance justifications, applicable
obligations). Low-confidence inference on those is itself a hazard. (Reinforces §15.)

Each skill mirrors the `archimate-modelling` philosophy (domain-driven thinking, Pareto/minimal-sufficient,
iterative) and embeds best-practice workflow + standards/legal pointers + guardrails (§15). **Progressive build:**
P2 `stpa-analysis`; P3 `cast-investigation` + `grc-management`; P5 adds GRC SBOM/CVE-context scripts; P6
`assurance-case`. A script ships only once its backing capability exists (verifier profiles P1c; connectors P5).

## 15. Guidance-first design (cross-cutting, first-class requirement)

Most users will **not** know these methods or the applicable legal/standards requirements. The
capability must actively assist them. Mechanisms:
- **`assurance_guidance` MCP tool** (analogous to `artifact_authoring_guidance`) returning per-step
  method guidance, when/why, and standards references (ISO 26262/21434/27001, ISO 31000, GDPR, NIST CSF).
- **Skills** walk the user through each method step-by-step, explaining intent, not just mechanics.
- **Document templates** with explanatory prompts and required sections.
- **Verifier messages that teach** — remediation hint *and* the rationale (e.g. why a safety constraint
  can't be "accepted").
- **Standards/obligation profiles** (§ attribute profiles) seeded so users can pick a framework and get
  the right fields and checks. Seed order for an automotive context: **ISO 26262 + ISO/SAE 21434** first,
  then ISO 31000 / ISO 27001 / GDPR.
- **Ask, don't assume** — skills request missing information (or point to the needed source) rather than infer
  low-confidence safety/security/legal judgements; low-confidence inference on those is itself a hazard (§14).

## 16. MCP surface — a separate, gated `arch-assurance` server **[RESOLVED]**

Add **new MCP server(s) next to `arch-repo-read` / `arch-repo-write`** so the modeling tool surface stays
small and uncluttered (honours the tool-count principle). Scoped to `module_class: assurance`.
- **Gated:** served **only** when the confidential assurance tier (§3.3) is configured *and unlocked*;
  otherwise the server does not start (fail-closed). No assurance content reaches an agent in a normal
  deployment.
- **Split RESOLVED → `arch-assurance-read` / `arch-assurance-write`** (mirrors the existing
  capability-constrained split; read-only agents get no mutate path).
- **Write-scope capability** (separation of duties): write scope is a composable axis
  `architecture | assurance | both | none` (`none` ≡ today's read-only). An analyst session runs
  `write-scope=assurance` — full assurance authoring, read-only on the architecture model — and therefore
  **cannot** execute the §7.1 "model this" action (needs architecture-write); it instead emits a *proposed
  modeling task* for an architecture-write session. That is a desirable SoD outcome, not a limitation.
  Assurance write **requires the encryption key**.
- **AI exposure control:** `arch-assurance-read` carries a **max-classification**; artifacts above it are
  excluded/redacted at the tool boundary unless explicitly opted in; exposure is logged (§23).
- Reuses the underlying write queue/cache (same backend) for consistency with model edits.

## 17. Verifier invariants (the "assurance engine" — where the philosophy is enforced)
Two levels: **(A) hard structural validity** (always enforced; blocks writes) and **(B) method-completion
profiles** (opt-in gates an analysis is *checked against* for sign-off; they report coverage, they don't block writes).

**(A) Hard structural validity + the safety safeguard**
- every `concern_class ∈ {safety,security}` constraint → has an `accountable-to` owner **and** (**`refines` ≥1
  requirement** [whose `realized-by` is the control measure] **or** a justified `enforcement_status`); **`disposition=accepted` rejected** without a
  justification doc + sign-off; a `risk.treatment=accept` cannot be the sole disposition of a safety hazard.
- every `unsafe-control-action` → references exactly **one `control-action`** (the STPA referent) + a controller.
- referential integrity of all assurance edges; `binding_status=unbound-pending` → **informational**, not error.

**(B) Method-completion profiles** (coverage gates for sign-off)
- `stpa-basic-complete`: every hazard → ≥1 loss; every UCA → ≥1 hazard **and** a control-action; every
  loss-scenario → explains ≥1 UCA; every UCA/scenario → ≥1 deriving constraint.
- `cast-complete`: a sealed `analysis_baseline` exists (§10); observed UCAs/scenarios trace to the incident;
  ≥1 corrective-action → constraint.
- `grc-control-coverage-complete`: every in-scope `obligation` → ≥1 constraint with a control measure, evidence,
  and an accountable owner; every `risk` → a treatment.
- coverage queries (informational): assets with no hazard linkage; constraints with no evidence; orphan UCAs/hazards.

## 18. Open decisions (consolidated)
Grouped by status; full rationale in the cited sections.

- **[RESOLVED]** Storage/confidentiality → pluggable `ConfidentialAssuranceStore` + immutable `AssuranceArchive`,
  SQLCipher default (**ADR-001, §26**). · Security = generic `hazard`+`concern_class` + reference vocab (§4.1).
  · MCP read/write **split** (§16). · UI = separate surfaces on shared engines, *not* the architecture-authoring
  chrome (§30 ¶3). · Threat/vuln + AI-BOM identification via module attribute-profiles + heuristics (§27.3, §29.1).
  · **Persistence** = the `ConfidentialAssuranceStore` (SQLCipher) is the **sole live source of truth**; the file
  layout is the export/private-git adapter format only (§3.2/§6). · **Cross-links** = bidirectional navigation,
  **one-way (assurance-side) persistence** (§6). · **Obligations** = assurance-owned `obligation` + public catalog
  refs (§6). · **UCA** references a first-class **`control-action`** (§4). · **CAST** requires a sealed temporal
  baseline (§10). · Verifier = hard validity + method-completion profiles (§17). · UI-boundary is a Phase-0 decision (§3.4).
- **[RESOLVED]** (confirmed): `assurance-constraint` = separate type + `level`, **`refines` an ArchiMate
  requirement** (implementation via the requirement's `realized-by`; **no `enforced-by`**) (§8); `risk` =
  first-class **optional** overlay, never governs safety (§9); **full CAST, Phase 3**, on the shared model (§10);
  **3 skills** (stpa/cast/grc) + `assurance-case` Phase 6 — as **directories**, designed-holistically /
  built-progressively, with an **ask-don't-assume** rule (§14).
- **[RESOLVED]** (confirmed): **matrices** = split by fit — generic `matrix` for traceability; bespoke UCA grid +
  risk heatmap; *no* heatmap logic in the generic renderer (§12). · **Key management** = staged — keychain
  single-key + `DELETE` by default; envelope/per-subject crypto-shred only for the immutable archive (Phase 4);
  pluggable key source (§26). · **Cross-module wildcards** = extend the loader now with **scoped `@module:class`**
  (frozen-at-load, inspectable via existing endpoints, startup-validated) (§4). · **`ai_role`** in the AI-BOM
  attribute-profile; **candidate-scan = one deterministic `arch-assurance-read` MCP tool**, skill-orchestrated (§27.3/§29.1).

**→ All §18 items are now [RESOLVED]. No open decisions remain; the plan is fully locked for build.**

## 19. Phased build order
**The canonical phased plan — Definitions of Done, checkable tasks, and the progress tracker — is §24.**
This section previously held a parallel provisional list; it was merged into §24 to keep a single source of
truth (Phases 0–7). Key cross-phase dependency: the control-structure diagram (Phase 2) depends on the
meta-ontology binding system being stable (already used by C4) — confirm before Phase 2.

## 20. Risks / trade-offs
- Ontology/scope creep — guard with the Pareto discipline in skills and a small entity set.
- Matrix heatmap likely needs a renderer extension.
- Control-structure binding depends on the meta-ontology binding system being stable (used by C4) —
  confirm before Phase 2.
- `module_class` touches generic frontend/registry code — must stay declarative (no hardcoded names).
- Keeping the assurance MCP surface small while covering STPA+CAST+GRC.

## 21. Sources (key)
- Leveson, *A New Accident Model for Engineering Safer Systems* — http://sunnyday.mit.edu/accidents/safetyscience-single.pdf
- STPA Handbook (Leveson & Thomas) — https://www.flighttestsafety.org/images/STPA_Handbook.pdf
- STAMP/STPA/CAST overview (UL) — https://www.ul.com/sis/blog/introduction-to-stamp-stpa-and-cast
- ArchiMate Risk & Security Overlay (Open Group W172) — https://publications.opengroup.org/w172
- STPA-Sec (data-flow adaptation) — https://pmc.ncbi.nlm.nih.gov/articles/PMC7959614/
- STPA + ISO 26262 — https://arxiv.org/pdf/1703.03657 ; ISO 26262 + 21434 co-analysis — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10975927/
- ISO 26262 safety requirement types — https://www.btc-embedded.com/iso-26262-requirement-types/
- Risk register design (ISO 31000) — https://thinkcloudly.com/blog/risk-register-aligned-with-iso-31000/ ; https://www.cerrix.com/en/insights/blog/what-is-a-risk-register-and-how-do-you-create-one
- STPA + MBSE traceability (Sandia) — https://www.sandia.gov/app/uploads/sites/273/2026/01/Security-Inclusive-Model-Based-Systems-Engineering-Project-1.pdf
- STPA + STRIDE for cyber loss scenarios — https://www.sciencedirect.com/science/article/abs/pii/S2214212620307857
- Ontological analysis & redesign of security in ArchiMate (COVER) — https://link.springer.com/chapter/10.1007/978-3-031-21488-2_6
- EU AI Act Art. 12 record-keeping (logs, ≥6-mo retention) — https://artificialintelligenceact.eu/article/12/ ;
  logging/immutability + Art. 18 10-yr docs — https://www.isms.online/iso-42001/eu-ai-act/article-12/
- EU CRA SBOM requirement (CycloneDX/SPDX, ~Dec 2027) — https://anchore.com/sbom/eu-cra/ ;
  https://fossa.com/blog/sbom-requirements-cra-cyber-resilience-act/
- AI-BOM / ML-BOM / agentic supply chain — https://repello.ai/blog/ai-bill-of-materials ;
  https://cloudsmith.com/blog/the-2026-guide-to-software-supply-chain-security-from-static-sboms-to-agentic-governance
- CycloneDX ML-BOM component types + modelCard (1.6) — https://cyclonedx.org/capabilities/mlbom/ ;
  https://cyclonedx.org/use-cases/ai-models-and-model-cards/
- AI asset discovery / shadow AI / MCP-server inventory (ingest, don't rebuild) — https://www.pillar.security/blog/ai-asset-inventory-the-foundation-of-ai-governance-and-security ;
  https://blog.qualys.com/product-tech/2026/03/19/mcp-servers-shadow-it-ai-qualys-totalai-2026
- STPA/MBSE tool UX (STPAmaster, XSTAMPP, Astah System Safety, Capella STPA viewpoint; usability×interoperability gap) — https://stpamaster.com/ ; https://astah.net/products/astah-system-safety/
- GRC UX (heat maps, control matrices, role dashboards) — https://hyperproof.io/resource/grc-platforms-features-you-need/
- Crypto-shredding for retention+erasure — https://en.wikipedia.org/wiki/Crypto-shredding ;
  WORM/immutable retention — https://www.smarsh.com/compliance-glossary/immutable-storage/
- PocketBase — https://pocketbase.io/docs/ ; SQLCipher — https://github.com/sqlcipher/sqlcipher ;
  Supabase RLS — https://supabase.com/docs/guides/database/postgres/row-level-security

---

## 22. Personas & user stories (with acceptance criteria)

**Personas**
- **P1 — Safety/Security Analyst** (knows the method, wants rigor + traceability).
- **P2 — Non-expert Engineer / Product Owner** (little method or legal knowledge; needs guidance).
- **P3 — Risk/Compliance Officer** (GRC: register, controls, obligations, evidence, audit).
- **P4 — AI Agent** (authors/queries analysis programmatically via MCP).
- **P5 — Architect / Model Owner** (consumes modeling-gap signals; owns the architecture model).

**US1 (P1/P2) — Conduct a proactive STPA.**
*As an analyst I can run losses → hazards → control structure → UCAs → loss scenarios → constraints,
guided.* **AC:** (a) each step is reachable via the `stpa-analysis` skill and `arch-assurance` tools;
(b) every artifact persists as a typed assurance entity with connections; (c) the analysis verifies
(invariants §17) before it can be marked complete; (d) a `stpa-analysis` document is generated linking
all artifacts (E155 enforced).

**US2 (P2) — Be coached as a non-expert.**
*As a non-expert I am told what each step means, why it matters, and which standard applies.*
**AC:** (a) `assurance_guidance` returns step intent + when/why + standards pointers; (b) doc templates
carry explanatory prompts; (c) verifier messages teach (remediation + rationale), e.g. why a safety
constraint can't be "accepted".

**US3 (P1/P3) — Safety is not silently priced away.**
*As an analyst I cannot close a safety hazard with a low risk score.* **AC:** (a) a `safety`/`security`
constraint with `disposition=accepted` and no justification doc + accountable sign-off **fails
verification**; (b) a `risk.treatment=accept` cannot be the sole disposition of a safety hazard;
(c) the failure message explains the safeguard.

**US4 (P1) — Security analysis without threat-catalog churn.**
*As a security analyst I classify hazards/scenarios with STRIDE/CWE/ATT&CK and update catalogs without
waiting on a release.* **AC:** (a) `(scheme, code)` classification validates against a versioned vocab
file; (b) adding a new catalog/version is a data change, no code/ontology edit; (c) `concern_class`
stays independent of classification.

**US5 (P1/CAST) — Learn from an incident.**
*As an investigator I run a CAST analysis reusing the control-structure model and produce corrective
constraints.* **AC:** (a) `incident` + `corrective-action` entities exist; (b) UCAs/scenarios carry
`mode=observed`; (c) corrective actions `derive` constraints that enter the same GRC lifecycle.

**US6 (P5) — Unmodeled structure surfaces as a modeling task.**
*As an architect I see when an analysis references structure not in the model and can model it in one
step.* **AC:** (a) unbound nodes appear as `modeling-gap` findings and render distinctly; (b) a guided
"model this" action creates the architecture entity and binds it (`binding_status→bound`); (c)
`out-of-scope` nodes are surfaced once, not repeatedly.

**US7 (P4) — Programmatic assurance authoring.**
*As an AI agent I create/query assurance artifacts via a dedicated MCP server.* **AC:** (a) assurance
tools live on `arch-assurance`, not on `arch-repo-*`; (b) read-only agents can be given read-only
assurance access; (c) structured verification feedback (codes + locations + hints) is returned.

**US8 (P3) — Risk register & control coverage.**
*As a compliance officer I see risks as owned entities and where controls/evidence are missing.*
**AC:** (a) `risk` entities have owners and link to hazards/scenarios + treating constraints; (b)
register/coverage are query/matrix views, not a separate store; (c) gaps (no evidence / no owner /
uncovered obligation) are reported.

**US9 (all) — Assurance never clutters the model.**
*As any user, browsing the architecture model I do not see assurance artifacts intermixed.* **AC:** (a)
frontend separates families by `module_class`; (b) assurance artifacts persist under `assurance/`, not
`model/`; (c) model stats/catalogs exclude assurance entities by default.

## 23. 🔴 Security, privacy, data-integrity & migration considerations

**Security & auth (new attack surface).** A new `arch-assurance` MCP server is the only new API surface.
- It **reuses the existing backend, write queue, and permission model**; assurance writes are gated
  exactly like model writes and **must respect `--read-only` and `--admin-mode`**.
- Provide the **read/write split** (`arch-assurance-read` / `-write`) so read-only agents get no mutate
  path (recommended; §16).
- No new auth/token logic introduced; no direct enterprise write outside admin mode.

**Privacy / confidentiality of findings (🔴 — RESOLVED, see ADR-001 §26).** Hazards, vulnerabilities and
loss scenarios are **sensitive analytical content** (threat-intelligence-like, not secrets). A layered
model, each layer matched to a distinct exposure vector:
1. **Rule 0 (hard):** never store secrets/exploit code/credentials/live keys; pre-commit secret scanning.
   Store references (CWE/CVE/ATT&CK IDs), not exploitation detail.
2. **TLP classification** (`confidentiality ∈ {clear, green, amber, red}`) on assurance artifacts — the
   metadata that drives layers 4–6.
3. **Minimise by default:** keep the queryable structural skeleton; keep sensitive detail thin / reference
   external systems (skeleton-vs-detail tiering, §E).
4. **File-level confidentiality = the confidential tier (§3.3):** separate repo + git-host access control,
   **plus default-on application-layer encryption at rest** (closes the host-compromise / backup / clone /
   git-history-permanence vectors that access control alone cannot). Index is ephemeral in-memory; rendering
   must be ephemeral/streamed (condition C1 below).
5. **AI boundary:** `arch-assurance-read` max-classification excludes/redacts above-threshold artifacts;
   exposure logged. *(Encryption does NOT cover this vector.)*
6. **Promotion gate:** promoting a classified/`security` finding to a wider-audience tier **warns and
   requires confirmation**; amber/red is blocked without sign-off.
- **Honest limits (documented for users):** backend RBAC ≠ file confidentiality; git history is permanent
  (classify *before* commit; promotion is the critical gate); crypto-in-git would defeat queryability, so we
  use adapter-level app encryption with an in-memory read model instead of git-crypt.
- **Condition C1 (blocker):** the assurance tier's diagram rendering must be **ephemeral/streamed** (never
  written plaintext to `diagram-catalog/rendered/`) or encrypted at rest — confirmed leak in
  `diagram_render.py`.
- **Condition C2 (blocker):** the §3.3 asymmetric-reference invariant + ID-only filenames.

**Data integrity & consistency.**
- Writes remain **atomic via the existing single write queue**; no multi-store transaction introduced.
- **Cross-module referential integrity** (assurance→architecture links) is enforced by the verifier;
  deletes use cascade/guard rules so connections never dangle.
- **Promotion is an atomic bundle** (entity + its connections); the §6 pre-check blocks orphaned
  `safety`/`security` constraints.
- `module_class` merge must not introduce duplicate element-class collisions (registry already raises
  on duplicate class names — assurance classes must be namespaced/distinct).

**Migrations (🔴 — but additive, file-based, no destructive DB step).**
- `module_class` added to the ontology/diagram-type **module protocol** with a **backward-compatible
  default `architecture`** (existing modules unaffected).
- Registry/bootstrap register the assurance module + diagram types + doc types + reference vocab.
- **Idempotent migrator** (pattern: `migrate_to_groups`) scaffolds the `assurance/` subtree + grouping
  axis into existing repos; safe to re-run.
- `types.generated.ts` **must be regenerated** (pre-commit hook enforces; `uv run tools/generate_types.py`).
- **Rollback** = unregister the module (data is purely additive; no architecture data mutated, so no
  destructive rollback path).

**Observability (advisory).** Log assurance writes + verification outcomes; emit assurance changes on
the existing SSE event bus; expose coverage-gap counts as stats.

**Domain-events rule — explicitly N/A.** The skill's "emit domain events for aggregate mutations" policy
targets event-sourced/aggregate systems. This is a **file/git-backed hexagonal store**; the existing
analogue (git commits + SSE notifications + the serialized write queue) already covers change capture.
No aggregate-event mechanism is in scope. *(Stated as an explicit skip per skill rules.)*

## 24. Implementation checklist & definitions of done (per phase)

_**This is the canonical progress tracker.** Update the status table and tick `[x]` items as work completes;
keep the top-of-file Status line in sync. Status values: ☐ not started · ◐ in progress · ☑ done._

| Phase | Scope | Status |
|---|---|---|
| 0 | Decisions + module extension mechanism (§29) | ☑ done |
| 1a | Confidential store + analysis-collection substrate | ☑ done |
| 1b | Assurance graph MVP — core types + MCP CRUD/verify (first vertical slice) | ☑ done |
| 1c | Immutable records + safety/structural verifier | ☑ done |
| 1d | Minimal UI surfacing (module_class plumbing, discoverability) | ☑ done |
| 2 | STPA (wizard, control-structure canvas, matrices, MCP, skill) | ☑ done |
| 3 | CAST + GRC depth (register, dashboards) | ☑ done |
| 4 | Storage breadth + governance depth (opt-in) | ☐ not started |
| 5 | Cybersecurity & supply-chain connectors (§27) | ☐ not started |
| 6 | Assurance cases & polish (GSN/bowtie, dashboards) | ☐ not started |
| 7 | Dogfood (model the system's own posture) | ☐ not started |

**Release gates (testable — each maps to a phase):**
- **G-a** no assurance artifact appears in model stats/catalogs by default (1b/1d).
- **G-b** with the store **locked**, the assurance MCP tools are absent / return nothing (1a).
- **G-c** every assurance mutation appears in the append-only hash-chained log (1c).
- **G-d** a low-risk `accepted` disposition on a *safety* constraint **fails** verification (1c).
- **G-e** a sample STPA analysis passes `stpa-basic-complete` (2).
- **G-f** rendered assurance diagrams never write plaintext to `diagram-catalog/rendered/` (2; condition C1, §23).
- **G-g** a CAST investigation without a sealed `analysis_baseline` **fails** `cast-complete` (3).

**Phase 0 — Decisions & module-class plumbing.** DoD: §18 confirmed; companion `plans/assurance-overlay/`
written; `module_class` in protocol/registry/bootstrap with default `architecture`; tests green;
`types.generated.ts` regenerated.
- [x] Confirm §18 decisions (esp. constraint class, risk entity, MCP split, skill set). All [RESOLVED].
- [x] Lock the **UI boundary** (§3.4): bespoke assurance surfaces on shared engines, *not* the architecture-authoring chrome.
- [x] **Module extension mechanism (§29):** `module_class` + `attribute_profiles` on protocols; `enabled`/`requires` manifest attrs; `config/settings.yaml` `modules:` block + `module_overrides()`; `is_module_enabled()` (fail-closed); `/api/modules` endpoint. See `plans/assurance-overlay/PHASE-0-module-extension.md`.
- [x] Write companion specs (Phase 0 spec at `plans/assurance-overlay/PHASE-0-module-extension.md`; Phase 1b entity/connection/profile specs deferred to Phase 1b start).

_Phase 1 is split into four thin vertical/horizontal slices so each lands and verifies independently._

**Phase 1a — Confidential store + analysis-collection substrate.** DoD: a store can be configured + unlocked,
fail-closed gating works (locked ⇒ no assurance tools, **G-b**), an empty analysis-collection group exists, nothing leaks to model views.
- [ ] `ConfidentialAssuranceStore` port + **SQLCipher adapter** (OS-keychain key, recovery-export, gitignored); in-memory read-model built from it.
- [ ] **analysis-collection** grouping axis (4th axis) + group create/list.
- [ ] `arch-assurance init|unlock|backup|export|rotate-key` lifecycle commands; fail-closed gating.
- [ ] one-way `assurance→architecture` ref resolver (tolerant of dangling refs).

**Phase 1b — Assurance graph MVP (first vertical slice).** DoD: create/query/**verify** the core STPA chain
through one `arch-assurance` read + write MCP path; assurance excluded from model stats/catalogs (**G-a**); no GUI beyond discoverability.
- [ ] `src/ontologies/assurance/` core types — `loss, hazard, control-structure-node, control-action, unsafe-control-action, assurance-constraint` — + permitted-rels (literal cross-module refs).
- [ ] module `attribute_profiles` (§29.1): `concern_class`, `disposition`, `uca_type`, TLP; always-on layers (no-secrets + secret-scan, classification, promotion gate).
- [ ] `arch-assurance-read` + `arch-assurance-write` MCP CRUD/query/verify (gated; write-scope). Regenerate `types.generated.ts`.

**Phase 1c — Immutable records + verifier.** DoD: every mutation lands in the append-only hash-chained log
(**G-c**); §17(A) hard validity + safety-disposition guard pass/fail correctly (**G-d**); modeling-gap findings emitted.
- [ ] `AssuranceArchive` port + append-only hash-chained audit log + sealable signed baselines + retention config (Art. 12 capability / 19–26 ≥6-mo / 18 10-yr).
- [ ] Verifier §17(A) hard validity + safety-disposition guard (US3); modeling-gap findings (§7.1, US6).
- [ ] Reference-vocabulary loader + STRIDE/CWE/ATT&CK + obligation-catalog seeds (§4.1); seed ISO 26262 / 21434 profiles first.

**Phase 1d — Minimal UI surfacing.** DoD: assurance has its own enabled-gated nav area and is discoverable; model catalogs exclude it.
- [ ] Frontend `module_class` plumbing (separate "Assurance" nav, exclude from model catalogs) + locked/unlocked banner. (Wizards/canvas are Phase 2, §3.4.)

**Phase 2 — STPA.** DoD: US1, US2, US4, US7, US9 acceptance criteria pass end-to-end.
- [x] `control-structure` diagram type (`module_class: assurance`, PUML renderer, `binding_status` visual cues, G-f guard in `diagram_render.py`).
- [x] `uca-matrix` diagram type (bespoke frontend grid; reuse generic `matrix` for traceability).
- [x] `stpa-analysis` doc type (8 required sections + E155 links; seeded in `engagement_repo_template.py`).
- [x] `assurance_stpa_complete` MCP tool (§17(B) coverage profile: 6 checks, gap report).
- [x] `assurance_model_this` MCP tool (3-step task spec for binding unbound-pending CSNs).
- [x] `stpa-analysis` skill directory (SKILL.md + references/ + assets/).
- [x] "Suggested model entities": W501 verifier + `assurance_model_this` task spec workflow (US6).

**Phase 3 — CAST + GRC depth.** DoD: US5, US8 pass.
- [x] `incident`/`corrective-action` + UCA/scenario `mode` + `cast-investigation` doc type + skill.
- [x] `risk` entity + register/coverage views + `grc-management` skill.
- [x] Obligation/compliance handling + `compliance-statement` doc + evidence links + promotion warnings.

**Phase 4 — Storage breadth + governance depth (opt-in).** DoD: a team can run PocketBase; regulated users
can enable WORM/legal-hold + crypto-shredding.
- [ ] PocketBase adapter (tool-managed sidecar option) + Supabase/private-git adapters behind the stable port.
- [ ] WORM/object-lock archive targets, legal-hold, eIDAS-qualified timestamping, crypto-shredding (per-record keys).

**Phase 5 — Cybersecurity & supply-chain connectors (§27).** DoD: an SBOM + CVE feed maps to model
components and contextualises STPA-Sec findings; an AI-BOM can be emitted from the model and reconciled
against a discovered one. Connect, don't rebuild.
- [ ] **Bidirectional `SecuritySignalConnector` port** (`import_bom` / `export_aibom` / `reconcile`; read-mostly; never gates earlier phases).
- [ ] **Ingestion ladder** (§27.1): GUI upload, CLI/MCP, CI Action+template → REST endpoint, registry/Dependency-Track pull, git-convention — with **persistent anchor mapping** + **idempotent versioned re-ingest**.
- [ ] SBOM ingest (CycloneDX/SPDX) → three-tier map (anchor / identity-match via `purl`/`cpe` / selective elevate); vuln ingest (OSV/NVD/Dependency-Track/CISA-KEV) + VEX.
- [ ] **AI-BOM**: emit CycloneDX 1.6 ML-BOM/ASBOM from the model (sealable into the archive) + ingest discovered + **reconcile/drift report**.
- [ ] **`ai-component` marking profile** (§27.3, opt-in) + heuristic candidate-scan (suggest & confirm) + coverage report; auto-mark on ingest / from the control structure.
- [ ] Optional ticketing (GitHub Issues/Jira) for the corrective-action loop.

**Phase 6 — Assurance cases & polish.** DoD: GSN/bowtie diagrams render; dashboards usable.
**Phase 7 — Dogfood.** DoD: this system's own posture modeled (separate effort).

## 25. Architecture quality-pass verdict

**Overall: Approve with conditions.** The design is goal-adequate (G1–G6 each trace to ≥1 user story
and checklist item), architecturally sound, and domain-pure: the assurance *domain* (ontology/method
concepts) is kept independent of infrastructure; `module_class` stays **declarative** so generic
components carry no domain logic (honours the modularity-boundary principle); persistence/transport/UI
remain in the outer layers.

**Conditions / blockers before build:**
1. **Confirm §18 decisions** — they shape the ontology and surface; building before they're locked risks
   rework.
2. **Confidentiality stance — RESOLVED** via ADR-001 (§26): confidential encrypted tier, layered model
   (§23). Remaining build-time conditions: **C1** ephemeral/encrypted rendering and **C2**
   asymmetric-reference + ID-only filenames (both §23).

---

## 26. ADR-001 — Confidential assurance storage: pluggable store + immutable records (convenience-first, progressive disclosure)

**Status:** Accepted direction (revised 2026-06-04; **supersedes** the earlier "AEAD-in-git default-on"
draft, which was premature). **Owner:** Michael Bauer.

**Context.** Assurance/STPA/CAST/GRC/cyber artifacts are sensitive *analytical* content (threat-intel-like,
not secrets). Audience = **personal projects + non-expert SMBs** with **no dedicated secure store** and
little ops capacity. The platform is git-backed, AI-native (MCP→LLM), and its artifact index is an
**in-memory read model** (confirmed). Two facts drive the decision: (a) for non-experts **convenience is a
security property** — if the safe path is hard, they bypass it (shadow storage, pasting into public chat);
(b) the **EU AI Act** requires, from day one, logging *capability* (**Art. 12**) with **≥6-month** log retention
(**Art. 19/26**) and **10-year** technical-documentation retention (**Art. 18**) — traceable/immutable, reaching
SMEs (high-risk *product* obligations from 2 Aug 2027). So immutable records cannot be a late bolt-on; a *minimal*
primitive ships from the start.

**Decision.**
1. **Pluggable storage via a `ConfidentialAssuranceStore` port** (hexagonal). Adapters: **SQLCipher**
   (embedded, encrypted — *default*), **PocketBase** (self-hosted, RBAC + REST API — teams), **Supabase/
   Postgres** (RLS — advanced), **private-git** (versioned — git-workflow users). The store is the *sole*
   home of the assurance graph; references are one-way `assurance → architecture` so git holds no
   confidential pointers. **Crypto is delegated to vetted stores — never bespoke.**
2. **Convenience-first default = SQLCipher with the key auto-managed in the OS keychain** (no passphrase
   ceremony), DB gitignored, one prompted **recovery-key export**, safe AI defaults. Encryption is simply
   *on*, invisibly.
3. **Fail-closed gating + guided enablement:** assurance MCP servers + GUI features exist only when a store
   is configured and unlocked; enabling is a guided one-command flow. `arch-assurance
   init|unlock|backup|export|rotate-key|verify` — users manage the store *through the tool*, not by copying
   files.
4. **Composable `write-scope` (architecture | assurance | both | none)** for separation of duties
   (assurance-only sessions; "model this" becomes a proposed task for an architecture-write session).
5. **Live store vs. immutable archive are separate concerns (two ports).** A second **`AssuranceArchive`
   port** holds immutable, signed, timestamped, append-only records, distinct from the mutable live store.
6. **Immutable records — minimal, get-go (EU AI Act):** ship from MVP an **append-only, hash-chained
   (tamper-evident) audit log** of assurance + system events with retention config (≥6-mo default, 10-yr
   option), plus **sealable signed baselines** of an analysis/safety-case at sign-off. Generic enough to
   serve Art. 12 logging + Art. 18 retention without committing to a still-unsettled specific schema.
7. **Heavy governance is progressive / opt-in (not MVP):** WORM/object-lock targets, legal-hold,
   eIDAS-qualified third-party timestamping, and **crypto-shredding (per-record keys)** to reconcile
   retention/immutability with GDPR erasure — enabled per deployment when a regulatory need is signalled.
8. **Always-on layers (adapter-independent):** Rule 0 (no secrets) + secret scanning; TLP classification;
   minimisation; MCP max-classification (the AI vector); promotion gate; asymmetric references.

**Consequences.**
- *Positive:* turnkey + encrypted-by-default for non-experts; immutable records present from day one
  (EU-AI-Act-ready) without overbuilding; storage flexible across personal→regulated; vetted crypto only;
  the safe path is the easy path.
- *Negative / accepted:* the storage-port abstraction (LCD API) + per-adapter read-model sync is real work
  → ship **port + SQLCipher first**, others behind the stable port; **cross-store referential integrity**
  (dangling `assurance→architecture` refs) needs a tolerant resolver; the OS-keychain key tie needs the
  recovery-export safeguard; **encryption never covers the LLM vector** (classification does);
  crypto-shredding is "not nirvana" for fine-grained erasure → per-record key granularity + minimisation.

**Key management & erasure — staged [RESOLVED].** Proportionate to the audience:
- **Default (live store):** a *single* DB key in the **OS keychain** (no passphrase ceremony) + recovery-export.
  Erasure on the mutable SQLCipher store is a normal **`DELETE`** — **no crypto-shred needed** at this tier.
- **Crypto-shredding (envelope: per-record/per-subject DEK wrapped by a KEK) applies ONLY to the immutable
  archive/WORM** (Phase 4, opt-in/regulated), where records can't be deleted in place. Granularity = the erasure
  unit (**per-subject** for GDPR personal data, per-finding otherwise) + minimisation.
- **Key source is pluggable:** keychain (default) → envelope / cloud-KMS / HYOK as advanced, *only where it earns
  its cost* (KMS ≈ $1/key/mo + ops). Not envelope-everywhere; not zero crypto-shred. Rejected both extremes.
- *Rejected:* AEAD-in-git default-on (negates git's value, history-permanence, bespoke-crypto risk);
  backend-only RBAC (can't protect files); mandatory WORM/heavy governance for all (over-build for the
  audience).

**Build-order impact:** MVP = `ConfidentialAssuranceStore` port + SQLCipher adapter (OS-keychain key) +
the minimal immutable-records primitive (append-only log + sealable baselines) + always-on layers.
PocketBase next; Supabase/private-git, WORM/legal-hold/crypto-shredding, and the cybersecurity connectors
(§27) later, behind stable ports.

**Strong recommendations:** split the assurance MCP server (read/write); seed ISO 26262 + 21434 first;
keep the entity set minimal (Pareto) and lean on classification/attributes over new types.

**Suggestions:** assess the matrix heatmap renderer extension early (it gates the risk-matrix UX);
confirm the meta-ontology binding system is stable before Phase 2 (control-structure depends on it).

**Traceability check:** G1–G6 → US1–US9 → §24 checklist items; all 🔴 concerns addressed in §23;
domain-events rule explicitly skipped with rationale. Open items consolidated in §18.

---

## 27. Cybersecurity & supply-chain integration — connect, don't rebuild

**Principle.** We do **not** reimplement scanners, SBOM generators, CVE databases, SIEM, or full
vuln-management/VEX engines — mature tools do these better (OWASP **Dependency-Track**, **OSV**, Trivy/Grype,
Snyk, Sonatype, Anchore, GitHub Advisory/Dependabot). **Our lane is contextualisation + connection:** linking
external security signals to architecture *structure* → STPA-Sec hazards/loss-scenarios → GRC controls →
immutable records. A CVSS 9.0 on an isolated component ≠ 5.0 on an internet-exposed one — *we* supply the
architectural + loss context scanners lack (the "dual-chain convergence":
[arch↔SBOM contextualisation](https://medium.com/@sylvain.ridoux/a-framework-for-converging-threat-modeling-as-code-tmac-and-vulnerability-operations-centers-2429f7499b2e),
[SBOM graph triage](https://arxiv.org/pdf/2604.04977)).

**Integrate via a pluggable, read-mostly `SecuritySignalConnector` port** (Phase 5; never gates the MVP):
- **SBOM ingestion (CycloneDX/SPDX)** → map components to architecture `application-component`/`node`/
  `artifact`. (EU **CRA** mandates SBOMs by ~Dec 2027 → common, growing use case;
  [CRA SBOM](https://anchore.com/sbom/eu-cra/).)
- **Vulnerability data (OSV / NVD / GitHub Advisory / CISA KEV, or via the Dependency-Track API)** → attach
  CVEs to mapped components; feed STPA-Sec hazards/loss-scenarios; contextualise by exposure + loss impact.
  Support **VEX** (affected / not-affected-in-context) to cut false-panic upgrades.
- **AI-BOM / ML-BOM (CycloneDX 1.6) for the agentic age** → inventory models, datasets, **MCP-server
  connections, tools, agent orchestration chains** ("every undocumented MCP server is an AI-BOM gap";
  [AI-BOM](https://repello.ai/blog/ai-bill-of-materials)). This system is itself agentic + MCP-based and
  STPA-Sec fits agentic control-structure analysis → a **differentiated** fit: ingest AI-BOM + model the
  agent control structure + retain immutable records (EU AI Act). Strong synergy with §3.3 / §26.
- **Ticketing / workflow (GitHub Issues / Jira)** → push corrective-actions, pull status (the GRC
  remediation loop). Optional.

**Guardrails.** Integration only where high-value *and* common; keep the MCP surface small; connectors are
read-mostly importers, **not background scanners**; phase **after** core assurance. The unique value is the
contextualised, retained chain **SBOM/CVE/AI-BOM → component → loss scenario → control → evidence →
immutable record** — which no scanner provides.

### 27.1 Getting BOMs in — an ingestion ladder (easy → automatic)
SBOMs are born in the build (syft, cdxgen, `trivy sbom`, native package plugins, GitHub export); meet them
there. A ladder so each user-class lands where it fits:
1. **GUI upload** — drop CycloneDX/SPDX, pick anchor. (personal / one-off)
2. **CLI / MCP** — `arch-assurance import-sbom <file> --anchor <entity>`; `assurance_import_bom` tool. (scripters/agents)
3. **CI step / published GitHub Action + GitLab template** → `POST /api/assurance/sbom` with a scoped token, every build. (SMB CI — the automatic path)
4. **Pull from source** — GitHub SBOM export, OCI registry attestations, or a **Dependency-Track** instance. (connect-once, stays fresh)
5. **Git convention** — a watched path (`*.cdx.json`) auto-ingested on sync. (zero-touch)

Two enablers make the automatic rungs hands-free:
- **Persistent anchor mapping** (`repo/path/PURL → entity_id`, declared once or auto-matched) so re-ingest never re-prompts.
- **Idempotent, versioned re-ingest** (keyed by anchor + BOM serial/version): update-in-place, diff vs prior, each version to the immutable log (doubles as CRA / AI-Act evidence).

**Store-reachability constraint (state plainly):** automatic CI ingestion needs a **network-reachable store**
→ PocketBase/Supabase or a shared backend; local-SQLCipher users stay on rungs 1–2 (ties to ADR-001). We do
**not** generate SBOMs (the build is the authority); at most an optional "run your installed syft/cdxgen for
you" convenience that clearly delegates.

### 27.2 Direction: SBOM import-only; AI-BOM bidirectional
- **SBOM = ingest-only.** The build knows the dependency closure better than any model; generating SBOM from the model would be wrong.
- **AI-BOM = round-trip.** The model is an authoritative source for the agentic inventory (models, datasets,
  inference APIs, **MCP servers, tools, agent chains**) — exactly what build tools miss. `export_aibom()`
  emits a **CycloneDX 1.6 ML-BOM/ASBOM** (component types `machine-learning-model`/`data` + `modelCard`); the
  emitted BOM is a governance deliverable (EU AI Act docs) that can be **sealed into the immutable archive**.
- **`reconcile()`** diffs the *modeled* AI-BOM against a *discovered* one (imported from runtime AI-discovery
  tools — Qualys TotalAI, MS Defender/Agent 365, etc. — or an AI-BOM file) → drift report ("runtime found MCP
  server C not in the model"). We do **not** do runtime discovery (those tools do it better); we ingest their
  output and add the modeled, contextualised, governed inventory + reconciliation.
- Connector port is bidirectional: `import_bom()` / `export_aibom()` / `reconcile()`.

### 27.3 Identifying & marking AI-BOM-relevant components (reliably)
Emitting a correct AI-BOM needs each element's **AI-BOM role + metadata**. No single mechanism is complete;
combine four layers, **authoritative-first**:
1. **Explicit marking = source of truth** — an **optional, declarative `ai-component` attribute profile** on
   relevant architecture entity types (application-component, system-software, application-interface,
   data-object, artifact, technology-service), **enabled with the AI-BOM capability so the base ontology stays
   clean** (no modularity-boundary violation; it's descriptive metadata, not assurance logic, and not a
   reference to assurance). Fields map to CycloneDX ML-BOM:
   - `ai_role` (machine-learning-model | dataset | inference-service | mcp-server | tool | agent | orchestrator | prompt | guardrail | vector-store | rag-pipeline) → CycloneDX component type;
   - identity `purl`/`cpe`/`component_ref` (matching + round-trip);
   - model/dataset metadata (provider, version, hosted/self-hosted, `external` = trust-boundary, model-card ref, dataset provenance/classification).
   **Mark easily:** a GUI "Mark as AI component" affordance with only `ai_role` required (progressive
   disclosure); bulk-confirm from candidate lists; agents via the edit tool.
2. **Heuristics = assistive (suggest & confirm, never authoritative)** — the heuristic instinct, made safe.
   **The scan is a deterministic `arch-assurance-read` MCP tool** (e.g. `assurance_scan_ai_candidates`) — *not*
   in-skill prose — so it returns a stable, testable ranked list reusable by GUI, agents, and CI **[RESOLVED]**.
   It ranks candidates by name patterns (gpt/claude/llm/embedding/dataset/mcp/tool/agent/rag/vector), connection/
   structure patterns (external component via an inference interface; a component an agent "uses"), domain, and
   provenance; the **skill orchestrates** scan → present → user/agent **confirms** → the profile persists.
   Heuristics cut the marking burden; they don't decide (false +/−).
3. **Provenance on ingest = auto-mark** — elements created/matched from an imported AI-BOM, a parsed **MCP/agent
   config** (`.mcp.json`, agent manifest — a reverse-architecture pattern), or a discovery-tool export are
   auto-typed + marked with provenance.
4. **Structured source = the agentic control structure** — once modeled for STPA-Sec, control-structure-node
   roles (controller = agent, controlled-process = tool/mcp) already encode AI-BOM roles → a purpose-built,
   reliable source.

**Completeness is a process, not a guarantee (honest stance):**
- **Coverage report** (modeling-gap pattern §7.1): heuristic-candidate-not-marked → prompt;
  marked-but-incomplete-profile → prompt. Classify **at creation/ingestion** to avoid an ungoverned backlog.
- **Drift reconciliation** (§27.2) catches what marking + heuristics miss.
- An emitted AI-BOM's completeness = f(marking discipline + ingestion coverage + reconciliation); the tool
  **states this** rather than implying completeness.

## 29. Module extension mechanism — attribute-profiles + feature flags

**Confirmed gaps (codebase).** `OntologyModule`/`DiagramTypeModule` protocols expose entity/connection types,
permitted-rels, bindings, bridges — but **no attribute-profiles**; today only per-repo
`.arch-repo/schemata/attributes.<type>.schema.json` declare those. And `app_bootstrap.py` registers
ontologies **unconditionally** — no enable flag, no `module_class`. Both are needed.

**29.1 Module-contributed attribute-profiles (the dedicated mechanism).** Extend the module protocol with an
optional **`attribute_profiles: Mapping[entity_type, JSONSchemaFragment]`**, shipped in the module (e.g.
`attribute_profiles/<type>.schema.json`) and **merged into the effective profile set only when the module is
enabled** — reusing the **same JSON-Schema attribute-profile format** as per-repo `.arch-repo/schemata/`. So:
- the **`ai_role` enum + model/dataset metadata** are declared by the AI-BOM module's profile fragment on
  `application-component`/`system-software`/`data-object`/… (answering §27.3 ¶1 — the enum is a *small stable
  schema enum* and rides the *existing* attribute-profile mechanism, **not** the evolving reference-vocab of
  §4.1, and not a bespoke mechanism); **[RESOLVED]**
- assurance `concern_class`/`disposition`/integrity-level/`risk`/TLP profiles are shipped by the assurance module.
- **Precedence:** module profile = defaults; per-repo schemata extend/override (additive; conflicts surfaced
  like the existing duplicate-element-class guard). Base ontology stays clean — profiles exist only when enabled.

**29.2 Feature-flag module toggles + `module_class`.** Layered, per the "registration *or* central config" ask
— use **both**:
- **Module manifest** declares `module_class` (architecture | assurance), default-enabled state, and
  `requires` (capability/module deps — e.g. assurance `requires: confidential_store`; AI-BOM `requires: assurance`).
- **Central `config/settings.yaml` `modules:` block** overrides per deployment.
- **Bootstrap** registers only enabled modules with satisfied deps (**fail-closed** — assurance won't enable
  without a store, consistent with ADR-001); a `/api/modules` endpoint exposes enabled modules + `module_class`
  so the **frontend renders nav/affordances conditionally**.
- Scope note: this is a **declarative registry-level toggle**, not a full feature-flag platform (OpenFeature et al.
  would be overkill).
- **Build on existing infrastructure (confirmed in code):** model-project groups already carry a
  **`meta_ontology` field** ("ontology framework restriction", `src/domain/groups.py`) and a `type_filter`,
  surfaced as the **"Framework" column + dropdown** in `GroupManagementView`. So per-group framework binding
  *already partly exists* — the assurance family reuses this (an analysis binds to the assurance meta-ontology +
  type-filters to assurance types), and the enabled assurance module simply appears in the framework dropdown.
  The remaining net-new pieces are `module_class`, module-contributed `attribute_profiles` (§29.1), the
  enable/`requires` gating, and the confidential store/subtree — not the framework-binding plumbing.

```yaml
modules:
  sysml_v2_min: { enabled: false }
  assurance:    { enabled: true }            # requires confidential_store
  ai_bom:       { enabled: true, requires: [assurance] }
```
Lands in **Phase 0/1**; unifies the earlier `module_class`, capability-gating, and `ai_role` threads into one
coherent extension contract.

## 30. User-flows & GUI integration (STPA/CAST/GRC ↔ modelling / diagramming / documenting)

**Research.** STPA/MBSE tools (STPAmaster, XSTAMPP, Astah System Safety, Capella STPA viewpoint) integrate STPA
with the system model so artifacts derive from one model — but **"no solution yet achieves both usability and
interoperability,"** and LLM-assisted STPA is only emerging. GRC UX favours intuitive flows, heat maps + control
matrices, and role-tailored dashboards that link findings back to objectives/regulations. **Our AI-native,
single-live-model platform is positioned to fill exactly that usability×interoperability gap.**

**Design principles.**
1. **One model, lenses not forks.** Assurance gets its **own top-level nav group** ("Assurance", visible only
   when enabled — beside Engagement/Global), but **deeply cross-links** into architecture. Back-references
   ("this component → N hazards/controls/CVEs/AI-role") are **computed in the read-model for authorised,
   unlocked sessions only — never persisted** into architecture repos (preserves the asymmetric-ref confidentiality).
2. **Guided, stepwise method flows (for non-experts).** A **"New STPA analysis" wizard** walks the 4 steps
   (purpose/losses → control structure → UCAs → scenarios → constraints) with what/why coaching + progress; a
   **CAST investigation** flow; a **GRC risk→treat→comply** loop. AI-assist offered at each step. Matches the
   STPA-tool norm + our guidance-first principle.
3. **Separate assurance *surfaces* on shared *engines* — do NOT ride the architecture-authoring chrome.**
   Distinguish three UI sub-levels (correcting an earlier over-reuse stance):
   - **Reuse (shared substrate):** rendering/compute engines (graph, PUML/diagram, **matrix**, treemap), the
     in-memory read-model + SSE + write-queue + persistence, the grouping/`meta_ontology`/`type_filter`
     mechanism, and the **design-system primitives** (nav shell, badges, tables). These are infrastructure, not
     architecture-modeling UI — rebuilding them causes waste + look-and-feel drift.
   - **Do NOT reuse for assurance authoring:** the generic ArchiMate **`EntityCreateView` form, the
     type-exhaustive connection picker, the domain-chip browse**. These embody artifact-driven architecture
     idioms; STPA/CAST/GRC are **workflow-driven**, so forcing them through this chrome is suboptimal.
   - **Build bespoke (driven by the assurance module via `module_class`):** the method wizards, the
     control-structure canvas (wrapping the graph/diagram engine), the UCA grid (wrapping the matrix renderer),
     the risk register + coverage dashboard, the mark/classify affordances, and the assurance browse/detail
     surfaces. The output is still normal queryable, traceable artifacts (so the model stays one graph), but the
     *experience* is purpose-built, not the architecture forms.
   Net effect: "entirely separate UI" at the **surface/flow** level, on a **shared shell + engines + design
   system + cross-links** — not a duplicated parallel app. Generic components stay free of `if (assurance)`
   branches (modularity-boundary); separation is driven declaratively by `module_class`.
4. **Contextual entry points + progressive disclosure.** An architecture entity's detail page gains an
   **"Assurance" tab** (when unlocked): hazards/risks/controls/CVEs/AI-role touching it; diagrams gain an
   "analyse for safety/security" action. Base UI stays uncluttered for users who never enable assurance.
5. **Dashboards & traceability (GRC norm).** Risk register + coverage/gap dashboard (modeling-gaps §7.1,
   uncovered hazards, missing evidence), role-tailored; a **clickable end-to-end traceability matrix**
   (loss→hazard→UCA→scenario→constraint→control→evidence) — the MBSE bidirectional-traceability value.
6. **Safe-by-default surfacing.** Locked banner when the store isn't unlocked; TLP/classification badges;
   AI-exposure indicators; promotion warnings.

Lands across **Phases 2–4** (wizards + control-structure canvas in P2; registers/dashboards in P3; contextual
tabs progressively). Differentiation = AI-native + single live model + guided + traceable.

### 30.1 Live GUI walkthrough — integration surfaces (per view)
Walked the running app (Playwright). Integration surfaces, mapped to actual views:
- **Entity detail (`/entity?id=…`):** the **Properties table** is where the `ai-component` profile + TLP/
  classification render (§29.1); add an **"Assurance" tab** (hazards/risks/controls/CVEs/AI-role touching the
  entity — computed in the read-model, **unlocked-only**, never persisted into architecture); the **Edit** flow
  hosts "Mark as AI component"/classify; header actions (Explore graph, Promote) gain "Analyse for safety/security".
- **Graph-explore (`/graph?id=…`):** prime surface for an **assurance lens** over the architecture graph —
  overlay hazards/controls/loss-scenarios around an entity, visualise SBOM/CVE contextualisation and §7.1
  modeling-gaps, and **render/edit the STPA control structure** (itself a graph).
- **Diagram author/display:** control-structure / bowtie / GSN as diagram types reuse the visual entity picker +
  binding + live preview + interactive SVG.
- **Document author/display:** STPA/CAST/risk/compliance docs reuse required-sections + entity-link authoring and
  display (the traceability narrative).
- **Matrices:** UCA / risk / traceability reuse matrix create/edit.
- **Group/Collection management:** assurance analyses organised via the grouping axes; the empty **"Framework"
  column** on Model Projects is the natural home for per-group ontology/`module_class` restriction (ties to §29).

A verbose, type-exhaustive connection picker on the entity detail (every type listed, incl. 0-count) means
assurance types must be **`module_class`-filtered** (§29) rather than interleaved — see §30 principle 3.

### 30.2 Optimal flows — grounded in the real GUI (reuse map + target experience)
The walkthrough refines the stance (§30 principle 3): **reuse the shared engines/substrate, build the assurance
*experience* as bespoke surfaces, and do not ride the generic architecture-authoring chrome.** Mapping by capability:

| Capability | Shared engine / substrate — **reuse** | Bespoke assurance surface — **build** (`module_class`-driven) |
|---|---|---|
| Navigation & grouping | grouping + `meta_ontology`/`type_filter` mechanism; nav shell + `EntityGroupNavTree` (axis-parameterized) + design-system primitives | an **"Assurance" nav group** + analysis workspace on a new **analysis-collection** axis |
| Entity authoring (losses/hazards/UCAs/constraints/risks) | read-model, persistence, validation, the attribute-profile schema engine (§29.1) | **method wizards** — *not* `EntityCreateView` / connection-picker; typed fields from the assurance profiles |
| Control structure / bowtie / GSN | graph + PUML/diagram renderer + binding system | **control-structure canvas** + `binding_status` rendering + graph-explore **assurance lens** |
| UCA / risk / traceability grids | the **matrix renderer** | bespoke **UCA grid / risk matrix / traceability** editors (matrix engine, assurance semantics) |
| STPA/CAST/risk/compliance narratives | the document engine (required-sections / E155) — schema-driven, not architecture-specific → reuse `DocumentCreate/Detail` as-is | doc types only |
| Contextual link from architecture | read-model back-ref compute (unlocked-only) | **"Assurance" tab** on entity detail + "Analyse" action |
| Live refresh / promotion | **SSE `/api/events`**; **PromoteView** + gate | subscribe assurance views; classification warnings |

The line: reuse the **renderer/engine**, not the **generic editor view** (reuse the matrix renderer, build a bespoke
UCA grid). Borderline schema-driven surfaces (documents, the axis-parameterized group-management view) are generic
enough to reuse as-is; the clear *don't-reuse* set is the ArchiMate entity form, the connection picker, and the
domain-chip browse.

**Optimal target experience (the thin guided layer):**
- **Assurance Browse** mirrors the existing Browse → groups → content pattern: lands on the analyses list
  (analysis-collection groups via `EntityGroupNavTree`); each analysis is a workspace bound to the assurance framework.
- **Guided method wizards are the primary authoring path** (not raw entity forms): "New STPA analysis" steps
  purpose/losses → control-structure (canvas) → UCAs (matrix) → scenarios → constraints, with what/why coaching +
  AI-assist; CAST and the GRC risk→treat→comply loop likewise. Each step is **bespoke UI on the shared engines**
  (graph/diagram, matrix, document) — not the generic entity form — yet writes normal, queryable, traceable artifacts.
- **Control structure** authored on a diagram canvas (drag existing model entities in as controllers/processes via
  the visual picker; unbound nodes ghosted + one-click "model this", §7.1) and explorable as an **assurance lens**
  in graph-explore.
- **Contextual "Assurance" tab** on the architecture entity detail (unlocked-only): hazards/risks/controls/CVEs/
  AI-role touching it; the **Properties** section renders the `ai-component`/TLP fields; an **"Analyse for
  safety/security"** action sits beside Explore-graph / Promote.
- **Risk register + coverage dashboard** reuse the table/treemap + matrix patterns; the **traceability matrix**
  (loss→…→evidence) is clickable end-to-end.

**Optimal-interface guardrails (from what the walkthrough exposed):**
- **`module_class`-filter the connection pickers** — the entity detail already lists *every* type (incl. 0-count);
  assurance types must not flood architecture pickers, nor vice-versa. Essential, not cosmetic.
- **Progressive disclosure** — none of the above is visible unless the module is enabled and the store unlocked;
  the base architecture UX is untouched for users who never opt in.
- **Native consistency** — assurance reuses the exact Browse/group/detail/SSE idioms so it feels built-in; the
  only genuinely new surfaces are the **wizards**, the **control-structure canvas**, the **risk/coverage
  dashboard**, and the **mark/classify** affordances.

Net: optimal on both axes — best UX (native idioms + guided method + contextual lenses) and best feasibility
(mostly reuse; small, well-scoped net-new surfaces). Wizards/canvas land in **Phase 2**, register/dashboard in
**Phase 3**, contextual tabs progressively.
