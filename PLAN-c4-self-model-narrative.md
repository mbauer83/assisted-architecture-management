# PLAN — Progressive C4 Self-Model & Narrative Arc for the Architecture Management Platform

Status: draft / proposal (rev. 2, incorporates design review)
Scope: ENG-ARCH-REPO engagement repository (the system's recursive self-model)
Author: architecture-modelling session, updated 2026-06-06

> **Rev-2 note.** A design review (13 findings) corrected several earlier decisions.
> The governing discipline is now explicit: **model the real target architecture
> first, then *project* C4 roles from it — never add ArchiMate elements or edges
> merely to satisfy the current projector.** The biggest changes from rev-1:
> (a) services are realized by **functions/processes**, *not* by application-components
> (§1.1, §3.1); (b) a new **application-component `Architecture Management Platform`**
> is the C4/structural root, with the existing service kept as its portfolio (§3.2);
> (c) the **C4 projector itself must be enhanced** before these views render correctly
> (§4); (d) assurance MCP is **mounted in the backend** — no separate assurance
> container; D4 scopes to an **Assurance Module grouping** (§3.4, §3.6); (e) **four**
> MCP bridges, not two (§3.3); (f) CLI modeling is **deferred** pending unification
> (§3.5); (g) a **repository-cleanup prerequisite** must reach zero errors first (§4).

---

## 1. Purpose & method

The system models itself in `ENG-ARCH-REPO`. The self-model is rich in *why*
(96 motivation entities) and *behaviour* (13 processes, 54 functions, activity
diagrams) but thin in *structure*: there is no C4 system-context, container, or
component view of the core system, and **no active-structure system root**. This plan
defines a top-down C4 arc (Context → Container → Component) and the prerequisite and
modelling work to make it real.

C4 views here are **model-backed projections**: a diagram is *scoped* to a model
entity and the projector derives boxes/edges from the ArchiMate graph (with
`_included_entity_ids` to bound scope). The review establishes that the projector, the
model's structural root, and several relationship semantics must change before the arc
is both *renderable* and *semantically correct*.

### 1.1 C4 ⇄ ArchiMate NEXT mapping (corrected)

| C4 element / view | ArchiMate NEXT | Notes |
|---|---|---|
| Person | `business-actor` / `role` | the human/agent active structure |
| Software System (scope) | **`application-component`** (active-structure root) | *not* a `service`; see §3.2 |
| Container | `application-component` (deployable); genuine **active** runtime store | a passive `data-object`/`artifact` is **not** a container |
| Component | `application-component` (module behind interface, nested) | responsibility = its assigned `function`(s) |
| Component responsibility | `function` (at-rest capacity), sequenced by `process` (in-motion) | `function`/`process` are common-domain in NEXT |
| **Service** (offered behaviour) | `service`, **realized by `function`/`process`** | active structure is **assigned to** behaviour; it does **not** realize the service |
| Dynamic view | `process` + existing activity diagrams | the behaviour story; not re-modelled as static C4 |
| Deployment view | `technology` | **out of scope** until deployment is a real question |

**The realization rule (review §3).** ArchiMate NEXT: a `service` is realized by
**behaviour** — `function --realization--> service` or `process --realization-->
service`. Active structure connects to behaviour by **`assignment`**
(`application-component --assignment--> function`). `application-component
--realization--> service` is **invalid** in either direction; a component and a service
may only **serve** or **associate**. Multiple behaviours may independently realize the
same service; a `grouping` or `and-junction` is needed only when their *combined*
contribution realizes it. → This plan does **not** create or reverse component/service
realizations; that audit belongs to the cleanup plan (§4).

### 1.2 Grounding (sources §9)

- **ArchiMate NEXT Snapshot 1** sharpens external **Service** vs internal
  **Process/Function** and makes behaviour **common-domain** (the repo already places
  all behaviour under `model/common/`). Service is realized by behaviour.
- **C4 (Brown):** a *container* is "a separately deployable/runnable unit that executes
  code or stores data"; a *component* is "a grouping of related functionality behind a
  well-defined interface", **not separately deployable**, decoupled from packaging; a
  *Dynamic diagram* shows runtime collaboration for a use case.
- **C4⇄ArchiMate (pre-NEXT Archi blog):** container→app-component, component→
  app-function, 1:1. Predates NEXT's unified behaviour; we diverge deliberately
  (component→app-component; behaviour carried by assigned functions) — §2.7.
- **ISO/IEC/IEEE 42010:** view↔model links are typed, n-ary **correspondences** — §2.8.

---

## 2. Diagnosis (what fits, what doesn't)

### 2.1 No active-structure backbone
Human `business-actor`s connect **only to `role`s**; `role`s connect to
**processes/functions**. The would-be root *Architecture Management System*
(`SRV@1778510457`) is a **service portfolio** (aggregates 6 services), not active
structure. There is no `person → system → container → component` spine, so C4 has no
structural root and no backbone to project from.

### 2.2 No container tier
28 `application-component`s sit in one flat namespace. Only *Architecture Backend*
(`APP@1777293133`) expresses internal structure, and it **omits** Model Verifier,
Frontmatter Parser, SQLite Indexer, Model Registry, Diagram Scaffolder, PlantUML
Renderer, Workspace Initializer. Whole-part uses `aggregation` (repo convention, 112
vs 6 compositions); we **retain aggregation** — the gap is *missing* edges, not kind.

### 2.3 External vs internal not distinguished
The four Agentic LLM Applications are external **agent hosts** but live in the internal
namespace, related only by `association` to the MCP Interface. Genuine external systems
(Git hosting, supply-chain signal sources) are **absent**.

### 2.4 Invalid / inconsistent relationships (delegated to cleanup, §4)
Service↔component **realizations are inverted and invalid** (e.g. `Authoring Service
--realization--> CLI Tool`; `Discovery Service --realization--> Query Engine`;
`Verification Service --realization--> Model Verifier`; `Model Verifier --realization
--> Python Runtime`). Per review §3 these are **not** mechanically reversed here — the
correct fix is behaviour→service chains, audited in the cleanup plan. The verifier also
misses illegal endpoint-type triples (review §12).

### 2.5 Behaviour is not assigned to structure
`function`s aggregate/trigger each other in a behaviour tree (`Full-Text Search` →
its parent function) and are **not** `assignment`-linked to the components that perform
them. The static C4 arc therefore renders from **structural edges + component
summaries**; we do **not** manufacture 54 assignments to feed C4 (review §13).

### 2.6 The projector cannot render these views yet (review §1, §2)
The current C4 projector: does **one-hop** containment only; has a **fixed** entity/
interaction set; **explicit inclusion only filters** candidates (cannot *add* missing
elements); **omits passive stores** from component views; does **not roll up** context
dependencies through internal containers; and **preserves ArchiMate direction**,
mislabelling `serving` as `uses`. None of D1–D4 will project correctly until this is
fixed. This makes projector enhancement a **first-class prerequisite**, not an
assumption.

### 2.7 What stays out of static C4 (and is fine)
`function`s (54), `process`es (13 → the **Dynamic** layer = existing activity
diagrams), `business-object`s (29), and file-granular `data-object`s do not appear in
static C4. Only genuine active runtime stores surface as containers; logical data is
*accessed*. The fine service tree stays in a service-decomposition view. No pruning
needed — these are adjacent viewpoints, not clutter.

### 2.8 Binding mechanics — identity 1:1, traceability may be n-ary
A C4 box's **identity** should be a single `represents` to one active-structure element
(round-trip + non-ambiguity). Richer links (`traces-to`/`refines`/`abstracts`) are
legitimate n-ary 42010 correspondences; `c4-uses` is **already 1:N** over connections.
**Recommendation:** keep entity *identity* 1:1; obtain responsibilities/services by
**graph traversal + projector roll-up**, not by multi-`represents`. A constrained
auxiliary-correspondence extension (≤1 `represents` + typed, graph-adjacent
`traces-to`) is principled but **not required** for this plan. Improve **derivation**,
not identity cardinality.

---

## 3. Target architecture corrections (model the real system, then project)

### 3.1 Behaviour → service chains
Keep the 6 `service`s as offered behaviour. Their realizers are **functions/processes**
(`function/process --realization--> service`); active structure is **assigned to**
behaviour. No `component --realization--> service` is created. The full audit/repair of
existing invalid realizations is owned by the cleanup plan (§4). For portfolio
traceability, **P1 establishes a *representative* set** of `component --assignment-->
function/process --realization--> service` chains — the principal **2–3 existing
behaviours per service** — enough to substantiate the offered portfolio richly,
**not** all 54 possible assignments (review §9).

### 3.2 Structural system root: **Architecture Management Platform** (new)
Create `application-component` **Architecture Management Platform (AMP)** as the C4
software-system and active-structure root.
- **AMP** `aggregation→` its top-level containers (Backend, Browser GUI, CLI client,
  the four MCP bridges).
- **AMP** `association` **AMS** (`SRV@1778510457`, the service portfolio) — this edge
  is **navigation only** and does *not* by itself substantiate "AMP offers the
  portfolio" (that comes from the §3.1 behaviour→service chains). AMP does **not**
  realize AMS.
- AMS remains the aggregation of the 6 services; those services are realized by
  functions/processes (§3.1).
- C4 scopes: **D1/D2 → AMP**; D3 → Backend; D4 → Assurance Module grouping.

### 3.3 Four MCP bridges (independently grantable trust boundaries)
Model four `application-component` bridges, each a thin stdio↔HTTP client of the
backend: **Architecture MCP Read Bridge**, **Architecture MCP Write Bridge**,
**Assurance MCP Read Bridge**, **Assurance MCP Write Bridge**.
- **Four distinct stdio `application-interface`s** — one per bridge (review §4). The two
  existing generic MCP interfaces cannot express four independently grantable read/write
  boundaries; create `Architecture MCP Read/Write` and `Assurance MCP Read/Write` stdio
  interfaces. (Do **not** also add four HTTP interfaces unless D3 needs endpoint-level
  detail.)
- Each bridge `assignment→` its own stdio interface; that **interface `serving→` the
  agent host(s)** that consume it (review §1 — this is the directed edge D1/D2 project,
  rendering `agent host --uses--> bridge`). **Architecture Backend `serving→` each
  bridge** (`bridge --uses--> Backend`).
- The existing `agent-host --association-- MCP Interface` links are **retained only as
  non-projected discovery** links (association is symmetric; not projected).
- Collapse the four visually **only in the context view**; show all four in D2.

### 3.4 Assurance runtime = mounted in backend (review §5)
Target: mount `/mcp/assurance-read` and `/mcp/assurance-write` in `arch-backend`
alongside the core endpoints (four endpoints total), returning structured
unavailable/locked status when assurance is disabled; the assurance UI stays hidden
until enabled; assurance STDIO commands become backend bridges (§3.3).

**"Fold" / "retire" as concrete model operations (review §3).** These are *migrations*,
not labels:
- **Reframe `MCP Model Server` (`APP@1712870400.kRZYOA`) → "Architecture MCP Endpoint
  Adapter"** and **`Assurance MCP Server` (`APP@1780656430`) → "Assurance MCP Endpoint
  Adapter"**: rename + re-summarize as **internal Backend components** (`Backend
  --aggregation-->` each), migrate their relationships (drop the invalid
  `service --realization--> adapter`; route data access through the proper
  behaviour/`access` paths), and exclude them from the container view (they are
  components, not containers). Where no meaningful endpoint implementation remains,
  **delete** the entity after migrating its edges. P3 owns this with explicit
  acceptance criteria (§4).

### 3.5 CLI topology — deferred (review §7)
The CLI presently mixes backend calls, direct repo access, direct config, and direct
assurance-store lifecycle ops. **Target:** non-init commands become **thin clients of
arch-backend** (the bridge pattern); **init/bootstrap commands stay independent** (they
must run before the backend exists). **Do not** model a single `CLI --serving-->
Backend` edge as the target. **Defer** final CLI container relationships until the CLI
unification lands; record it as a **prerequisite/dependency** (§4). In D2 the CLI client
appears, with its precise edges marked provisional.

### 3.6 Assurance Module — a concern boundary, not a deployment boundary (review §9)
Create common-domain `grouping` **Assurance Module** corresponding to the real
`module_class: assurance` boundary. It groups: Assurance Verifier, Supply-Chain &
Vulnerability Connector, Assurance Archive, Confidential Assurance Store, and the
relevant stores. It is **D4's scope** (concern-scoped view) and does **not** assert
separate deployment — the Architecture Backend remains the in-process runtime owner.
(Requires projector grouping-scope support, §4.)

### 3.7 Stores — active vs logical (review §8)
Apply the ontology faithfully:
- **Backend (or its behaviour) `access→` logical `data-object`s** (e.g. SQLite Index,
  Assurance Knowledge Base, Bill of Materials, Security Signals Store).
- **Artifacts realize data-objects** (`SQLite Database --realization--> SQLite Index`;
  `Git Repository`, `Encrypted Assurance DB`, `Security Signals DB` realize their
  logical objects).
- **Baseline decision — closed (review §7):** the default assurance store is
  **SQLCipher, embedded/in-process** (`store_factory.py`), so the **standard D2 has no
  active-store container**. Logical stores are *accessed*; their backing artifacts
  *realize* the data-objects.
- **PocketBase variant — model it (built capability).** PocketBase is **implemented**
  (`PocketBaseAssuranceStore` + `pocketbase_lifecycle.py`, selected via
  `store_backend: pocketbase` + `ARCH_POCKETBASE_URL`) — a real self-hosted, out-of-
  process store, already modelled as `system-software PocketBase`. Model it as a
  **documented optional variant**: `PocketBase --serving--> ` the assurance store
  adapter, surfaced as an active-store **container** in a variant D2. This requires
  **admitting `system-software` as an active-store C4-container role** (the c4-container
  ontology bridges `container → application-component`/`service` only — add a
  `system-software` bridge). Baseline D2 (SQLCipher embedded) still shows **no** store
  container.
- **Do not** invent active store components solely to obtain C4 boxes.

### 3.8 Context actors — real interactions only (review §10)
Eight actors belong in D1: Architect, Developer, Product Owner, Upper Technical
Management, DevOps/operator, AI Agent, Safety/Security Analyst, Risk/Compliance
Officer. Their context edges derive from **real interface usage** (interface `serving→`
actor), rolled up to AMP — **no** artificial `AMP --serving--> actor` edges. Confirmed
surfaces:
- **Web/GUI** serves **all human actors** (the primary human surface).
- **MCP** serves the **AI Agent** host and **Product Owner / Upper Technical Management**
  (management consume via MCP reporting, typically agent-assembled).
- **CLI** serves **Developer / DevOps**.
- **Assurance** surfaces serve **Safety/Security Analyst & Risk/Compliance Officer**.
- **REST is *not* actor-facing** — it backs the GUI and connecting tools only; it does
  **not** `serving→` any actor.

### 3.9 External systems (review §11)
- **Agent host** — **one generic external system** (e.g. *AI Agent Host*), not the four
  form-factor entities (CLI/Desktop/IDE/Web are the same product and used for coding,
  planning, reporting, and research alike). Collapse the existing four Agentic LLM
  Application entities into this one; fold the foundation-model dependency into its
  *description* (no separate Foundation-Model Provider). Capability (read/write/
  assurance) lives on the **bridges**, not the host; the host's directed C4 edge comes
  from each bridge stdio interface `serving→` the host (§3.3).
- **Git Hosting** and **Supply-Chain Signal Sources** are separate external systems.
  Directions matter under serving-reversal (review §2):
  - **`Git Hosting --serving--> Git Sync Service`** (hosting provides the remote/API the
    sync consumes → renders `Git Sync uses Git Hosting`). Add `flow` edges for push/pull
    **only** if a dynamic view needs them — not for D2.
  - **`Supply-Chain Signal Sources --flow--> Supply-Chain Connector`** (signals flow in).
- **Exclude** a standalone foundation-model provider from the AMP context view.

---

## 4. Prerequisites & dependencies (gate the C4 views)

Each prerequisite names what C4 needs. Gating is **per-view, not global** (§6): e.g. D1
needs P1+P2 but not P3/P4, while D2 needs P3+P4.

**P1 — Repository cleanup (review §12), owner: `PLAN-archimate-next-rule-conformance-and-repository-cleanup.md`.**
Reconcile ontology rules with the normative matrix; enforce relationship legality on
every write; add repo-wide semantic verification (incl. illegal endpoint-type triples);
repair invalid relationships/diagrams (including the §2.4 realizations via proper
behaviour→service chains); migrate/relocate legacy documents; normalize requirement
attributes. **Acceptance: zero verifier errors.**

**P2 — C4 projector enhancement (review §1, §2).** *Not greenfield:* builds on
`c4_scope_projection.py` (Phase 3 connection-class-aware derivation:
`_NESTING_TYPES` vs `_NEIGHBOR_TYPES`) and the **done** `plans/meta-ontology-v2/
PLAN-c4-renderer-fix.md` (2026-05-31), which already excludes aggregation at context
level and labels `serving`→"uses". **Remaining delta** — note the renderer fix changed
the *label* but **not the edge direction**, so direction-reversal is still open:
- configurable **containment**, **interaction**, and **store** roles;
- **additive, validated inclusion** (inclusion can *add* graph-justified elements, not
  only filter);
- **bounded context roll-up** of dependencies through internal containers;
- **passive-store dependencies** surfaced in component views;
- **grouping scope** support (for §3.6 concern views);
- **relationship projection fixes:** reverse `serving` → `Consumer --c4-uses-->
  Service`; preserve `flow`/`access`/`triggering` direction; treat `association` as
  neighbour-discovery only, emitting a directed edge **only** when direction comes from
  another relationship, explicit diagram metadata, or a deterministic role rule; align
  projected types with the C4 binding declarations;
- **deterministic traversal** + size limits;
- **tests** for preview/derivation/refresh/render parity.

**Roll-up acceptance contract (review §5) — make "bounded roll-up" testable:**
traverse `containment* → interaction → containment*` within defined boundaries; **stop**
at external systems and at selected scope roots; **reverse `serving` before roll-up**;
**remove self-loops**; **merge equivalent C4 edges** into one; **bind that one C4 edge
to all contributing model connections** (retain path provenance); apply a
**deterministic label-precedence** rule so multi-path edges get stable labels/directions
(no duplicates, no conflicting directions).

**P3 + P4 — Backend runtime unification.** **Owner: `PLAN-backend-runtime-unification.md`**
(all MCP + all artifact-affecting CLI route through `arch-backend`; bootstrap/config CLI
stays independent). C4 needs from it: four MCP endpoints mounted in the backend; four
thin stdio bridges (the bridge containers, §3.3); MCP Model Server / Assurance MCP Server
reframed as Backend-internal **endpoint-adapter** components (§3.4) — confirmed
**reframe, not delete** (both are real mounted FastMCP implementations); the unified CLI
as a thin backend client (enables §3.5/D2). That plan also **supersedes** the stale
"separate Assurance MCP Server" modelling in `PLAN-assurance-architecture-model.md`.

---

## 5. Model-change groups (additive, safe; run after/with P1)

All via `arch-repo-write`, `dry_run=true` → check `verification` → `dry_run=false`;
`artifact_save_changes` per group; repo-wide `artifact_verify` at the end. These groups
add the **target structure**; they do **not** touch the §2.4 realizations (that is P1).

- **Group R (root):** create AMP (§3.2); `AMP --aggregation--> {Backend, Browser GUI,
  CLI client, 4 bridges}`; `AMP --association-- AMS`.
- **Group B (bridges):** create the 4 MCP bridges + **4 distinct stdio interfaces**
  (§3.3); `Backend --serving--> each bridge`; `bridge --assignment--> its own stdio
  interface`; `stdio interface --serving--> agent host`; reframe MCP Model Server /
  Assurance MCP Server as Backend-internal endpoint adapters (P3, §3.4).
- **Group K (backend whole-part):** `Backend --aggregation-->` the 7 omitted components
  (§2.2) so D3 derives all 15.
- **Group M (assurance module):** create `grouping` Assurance Module (§3.6);
  `Assurance Module --aggregation/composition--> {Assurance Verifier, Supply-Chain
  Connector, Assurance Archive, Confidential Store, relevant data-objects}`.
- **Group S (stores):** apply §3.7 — `artifact --realization--> data-object`;
  `Backend --access--> data-object`; **baseline elevates no store to a container**
  (only the optional PocketBase variant).
- **Group X (external + actors):** create Git Hosting, Supply-Chain Signal Sources
  (external); **`Git Hosting --serving--> Git Sync`** (corrected direction);
  `Supply-Chain Sources --flow--> Supply-Chain Connector`; mark the 4 agent hosts
  external (fold LLM dep into descriptions). Add **real** interface→actor `serving`
  edges for the 8 actors (§3.8); agent-host edges via bridge interfaces (Group B).
- **Group D (delegated):** the realization-direction/legality audit is **owned by P1**,
  not done here.

---

## 6. The C4 diagram arc (per-view gates; the 5-view narrative, review §13)

Each view has its **own gate** — do not block all five on all prerequisites (review §6):

| # | Type | Scope | Shows | Question | **Gate** |
|---|---|---|---|---|---|
| **D1** | `c4-system-context` | AMP | 8 actors; agent hosts, Git Hosting, Supply-Chain Sources (external) | Who uses the platform, and what sits around it? | P1, P2, **R, B, X** |
| **D2** | `c4-container` | AMP | Browser GUI, unified CLI, 4 MCP bridges, Backend (no active store at baseline, §3.7) | What are the runtime pieces and how do all paths funnel through the backend? | P1, P2, **P3, P4** (no provisional final) |
| **D3** | `c4-component` | Architecture Backend | the 15 internal modules as a **backend responsibility overview** | What are the backend's modules and responsibilities? | P1, P2, **K**, endpoint migration |
| **D4** | `c4-component` | **Assurance Module** (grouping) | Assurance Verifier, Supply-Chain Connector, Archive, Confidential Store + accessed data | How does assurance stay linked to the model yet confidential & tamper-evident? | P1, P2, **P3, M, S** |
| **D5** | (reuse, **layered** — §6.1) | per level | existing `process`/activity diagrams as **dynamic/use-case** views, mapped to the level each belongs to | What does each level actually *do* at runtime? | P1 + activity-diagram cleanup |

Notes: **D3 is the responsibility overview**, not the consistency story — reuse an
existing dynamic diagram (e.g. *From Write to Consistent State*) for write-serialization
rather than forcing it into a 15-box static view (review §8). D2 shows the four bridges
explicitly (collapsed only in D1) and waits for **P4** so the unified CLI is modelled
correctly — no provisional CLI edges in a final diagram. **No deployment view** until
deployment is a real architectural question. Cross-navigation comes from each box's
single `represents` binding (§2.8).

### 6.1 Dynamic / use-case views are layered (not a flat set)

The behaviour story attaches at the level it belongs to:
- **Platform use-case layer (with D1/D2) — what users *do*:** architecture **planning**,
  **review/conformance**, **reverse-architecture**, and **assurance** (planning, review,
  analysis, case-building, incident investigation, risk & compliance), plus **querying &
  navigation** (standalone and embedded in planning/review). Existing diagrams:
  *Architecture Modelling & Planning*, *Architecture Conformance Review*, *Reverse
  Architecture*, and the assurance processes (*Conduct Hazard Analysis*, *Build Assurance
  Case*, *Investigate Incident*, *Manage Risk & Compliance*). **Gap:** a query/navigate
  use-case view likely needs authoring.
- **Management / technical workflow (with D2):** *Promote Artifacts*.
- **Backend-internal dynamics (with D3):** *From Write to Consistent State*, *Execute
  Staged Bulk Operation* — lower-level application/consistency concerns; reuse for D3's
  serialization story rather than inflating the static component view.

---

## 7. Sequencing

Decision: **additive modelling runs in parallel with the prerequisites** (the new
entities collide minimally with cleanup).
1. **In parallel now:** (a) additive **Groups R/K/M/S/X** (new structure); (b) **P1**
   cleanup (owns the realization audit/legality, §2.4); (c) **P2** projector; (d)
   **P3+P4** backend unification (`PLAN-backend-runtime-unification.md`).
2. **Author each view when its per-view gate (§6) is met** — not all five at once.
3. **Highest value first:** Groups R/K + P1 + the projector serving-reversal unlock
   **D1** and **D3** soonest; **D2/D4** follow P3/P4 (unification) and M/S.

---

## 8. Open decisions

- **Active-store determination — CLOSED (§3.7, review §7):** baseline has **no**
  active-store container (SQLCipher embedded, per `store_factory.py`); the optional
  PocketBase variant is the only out-of-process case.
- **AMP ↔ AMS edge — CLOSED:** `association`, navigation-only (review §4/§9).
- **Assurance Module realization — CLOSED:** the grouping does **not** realize the
  service (review §9); behaviour→service chains (P1) carry portfolio traceability.
- **Remaining:** confirm which agent hosts are read-only vs write-capable (drives which
  stdio interface serves which host, §10.3/§10.7).

---

## 9. Sources

- **Normative (relationship legality):** `ArchiMate-NEXT-Snapshot-1-connection-rules.pdf`
  (the supplied connection-rule matrix) — authoritative for permitted endpoint/relation
  triples; P1 reconciles the ontology to it.
- *Explanatory only:* ArchiMate NEXT Snapshot 1 (Open Group S250) summaries; R&A /
  G. Wierda, *ArchiMate NEXT: At your service!* (ea.rna.nl, 2026-01-26).
- C4 model (Simon Brown): c4model.com — `/abstractions`, `/abstractions/component`,
  `/diagrams/dynamic`.
- C4⇄ArchiMate (pre-NEXT, 1:1): archimatetool.com blog, *C4 Model, Architecture
  Viewpoint and Archi 4.7* (2020-04-18).
- ISO/IEC/IEEE 42010 — correspondences & correspondence rules (typed, n-ary).

---

## 10. Execution spec (run after P1; §1–§9 are rationale)

Edge legend (archimate-): **R**=realization · **S**=serving · **Ag**=aggregation ·
**Ac**=access · **As**=assignment · **Fl**=flow · **Asc**=association. Every write:
`dry_run=true` → check `verification` → `dry_run=false`. `artifact_save_changes` per
group; `artifact_verify(repo_scope="engagement", return_mode="full")` at end.
**Do not** create or reverse any `service`↔`component` realization — that is P1.

### 10.0 Entity ID reference
| Name | ID |
|---|---|
| Architecture Management System (service portfolio) | `SRV@1778510457.fu8ZS1` |
| Architecture Backend | `APP@1777293133.OYEmP1` |
| Browser GUI / CLI Tool | `APP@1776149382.lmO0mp` / `APP@1712870400.kjC6ex` |
| MCP Model Server (fold into Backend) / Assurance MCP Server (retire, P3) | `APP@1712870400.kRZYOA` / `APP@1780656430.m-U5S1` |
| Git Sync Service | `APP@1777293134.tY3JIK` |
| Backend comps to aggregate (K): Model Verifier / Frontmatter Parser / SQLite Indexer / Model Registry / Diagram Scaffolder / PlantUML Renderer / Workspace Initializer | `APP@1712870400.ca3vm7` / `.YOOEbL` / `.JOmFWy` / `.yNhgdh` / `APP@1776633697.SCKD2U` / `APP@1777293136.yaxrWl` / `APP@1776633694.w51oVF` |
| Assurance comps: Verifier / Supply-Chain Connector / Archive / Confidential Store | `APP@1780656431.XFD85E` / `.e2zPs6` / `.GnsLC8` / `.E0fzqZ` |
| Logical data-objects: SQLite Index / Assurance KB / Bill of Materials / Security Signals Store | `DOB@1712870400.3rilik` / `DOB@1780656431.ApaPcg` / `.dRnK-o` / `.p04R7k` |
| Artifacts: SQLite Database / Git Repository / Security Signals DB / Encrypted Assurance DB | `ART@1712870400.FtioFJ` / `ART@1712870400.YsLpM8` / `ART@1780656477.X7EfZb` / `.tkNvK_` |
| system-software: PocketBase / SQLCipher / Python Runtime | `SSW@1780656477.kIOyT2` / `.nhzGvk` / `SSW@1712870400.o7a0ad` |
| Interfaces: CLI / REST / MCP / Web / Assurance MCP | `AIF@1712870400.KxvY-B` / `AIF@1712870400.XjbNQh` / `AIF@1712870400.wuleEe` / `AIF@1776149386.Ua50xU` / `AIF@1780656431.cdcRZG` |
| Actors: Architect / Developer / DevOps / Product Owner / Upper Tech Mgmt | `ACT@1712870400.Nn7Oo7` / `.Pp8Qq8` / `.OLWiNc` / `.Rr9Ss9` / `.Ut1Vv1` |
| Roles: AI Agent / Risk&Compliance Officer / Safety-Security Analyst | `ROL@1776633082.udXPfB` / `ROL@1780656241.abNYhO` / `ROL@1780656241.yswDMB` |
| Agent hosts (external): CLI / Desktop / IDE / Web | `APP@1777390179.N96vdO` / `APP@1777390180.AUw6Qr` / `APP@1777390182.PaedDQ` / `APP@1777390183.27nbQ9` |

### 10.1 Create entities (`artifact_create_entity`) — capture returned IDs
- `application-component` **Architecture Management Platform** — "The complete software
  product: active-structure root aggregating the backend, GUI, CLI, and MCP bridges.
  Associated (navigation) with the Architecture Management System service portfolio,
  which behaviour realizes." → `$AMP`
- `application-component` ×4 bridges (thin stdio↔HTTP clients of the backend):
  **Architecture MCP Read Bridge** `$ARDB`, **Architecture MCP Write Bridge** `$AWRB`,
  **Assurance MCP Read Bridge** `$SRDB`, **Assurance MCP Write Bridge** `$SWRB`.
- `application-interface` ×4 (distinct stdio surfaces, one per bridge):
  `$IARDB`, `$IAWRB`, `$ISRDB`, `$ISWRB` (review §4).
- `grouping` **Assurance Module** — "Concern boundary (module_class: assurance) grouping
  assurance verifier, connectors, archive, and confidential stores; in-process in the
  backend." → `$ASMOD`
- `application-component` (external) **Git Hosting** `$GITHOST`; **Supply-Chain Signal
  Sources** `$SUPPLY`. *(No standalone foundation-model provider — review §11.)*
- `application-component` (external) **AI Agent Host** `$HOST` — "Generic agent harness
  (CLI/desktop/IDE/web; coding, planning, reporting, research) that drives the platform
  via the MCP bridges; embeds its own foundation-model dependency." Assign the **AI
  Agent** role to it; then **retire the 4 Agentic LLM Applications** — migrate their
  edges to `$HOST` and `artifact_bulk_delete` the four.
- **Endpoint adapters (P3 migration):** rename `APP@1712870400.kRZYOA` → "Architecture
  MCP Endpoint Adapter" and `APP@1780656430.m-U5S1` → "Assurance MCP Endpoint Adapter"
  (`artifact_edit_entity` name+summary); both become Backend-internal (§10.3).

### 10.2 Group R (root)
`$AMP` **Ag→** Backend, Browser GUI, CLI Tool, `$ARDB`, `$AWRB`, `$SRDB`, `$SWRB`.
`$AMP` **Asc–** AMS.

### 10.3 Group B (bridges, interfaces, endpoint-adapter migration)
- Backend **S→** `$ARDB`, `$AWRB`, `$SRDB`, `$SWRB` (bridge uses Backend).
- Bridge **As→** its own stdio interface: `$ARDB`→`$IARDB`, `$AWRB`→`$IAWRB`,
  `$SRDB`→`$ISRDB`, `$SWRB`→`$ISWRB`.
- Each stdio interface **S→** the agent host(s) that consume it (read interfaces serve
  read-only hosts; write interfaces serve write-capable hosts) — these are D1/D2's
  directed host edges. Keep old `agent-host —Asc— MCP Interface` as non-projected
  discovery.
- **Endpoint adapters:** Backend **Ag→** "Architecture MCP Endpoint Adapter" and
  "Assurance MCP Endpoint Adapter"; remove any `service --R→ adapter` edges on them
  (locate via `find_connections_for`); exclude both from D2 (they are components).

### 10.4 Group K (backend whole-part)
Backend **Ag→** Model Verifier, Frontmatter Parser, SQLite Indexer, Model Registry,
Diagram Scaffolder, PlantUML Renderer, Workspace Initializer (7 edges).

### 10.5 Group M (assurance module)
`$ASMOD` **Ag→** Assurance Verifier, Supply-Chain Connector, Assurance Archive,
Confidential Store, Assurance KB, Bill of Materials, Security Signals Store.

### 10.6 Group S (stores — §3.7)
`SQLite Database --R→ SQLite Index`; `Backend --Ac→ SQLite Index`; analogous
`artifact --R→ data-object` for Git Repository / Encrypted Assurance DB / Security
Signals DB. **Baseline: no active-store container** (SQLCipher embedded). Only for the
optional PocketBase variant add `PocketBase --S→` the assurance store adapter (and the
c4-container ontology `system-software` bridge) — not in baseline D2.

### 10.7 Group X (external + real actor interactions)
- **`$GITHOST` S→ Git Sync Service** (hosting serves the sync — NOT the reverse);
  `$SUPPLY` **Fl→** Supply-Chain Connector.
- Single external **`$HOST`** replaces the 4 agentic apps (§10.1); the four bridge stdio
  interfaces **S→ `$HOST`** carry its directed edges (`external: true`).
- Real interface→actor serving edges (§3.8): **Web Interface S→** all 5 human actors;
  **MCP Interface S→** {AI Agent, Product Owner, Upper Tech Mgmt}; **CLI Interface S→**
  {Developer, DevOps}; **assurance surfaces S→** {Safety-Security Analyst, Risk&
  Compliance Officer}. **REST Interface: no actor edges** (GUI/tools only). No artificial
  AMP→actor edges.

### 10.8 Diagrams (`artifact_create_diagram`; honour the **per-view gates** in §6)
- **D1** (gate P1,P2,R,B,X) `c4-system-context`, scope=`$AMP`. person[]: 5 actors + 3
  roles. software-system[]: `$HOST` + `$GITHOST` + `$SUPPLY`, `external:true`.
- **D2** (gate P1,P2,P3,P4) `c4-container`, scope=`$AMP`. container[]: Backend, Browser
  GUI, unified CLI, `$ARDB`, `$AWRB`, `$SRDB`, `$SWRB`. **No active-store box** at
  baseline (§3.7); no provisional CLI edges — wait for P4.
- **D3** (gate P1,P2,K,endpoint-migration) `c4-component`, scope=Backend. component[]:
  the 15 backend comps; `_included_entity_ids` += SQLite Index. Responsibility overview;
  reuse a dynamic diagram for the consistency story.
- **D4** (gate P1,P2,P3,M,S) `c4-component`, scope=`$ASMOD`. component[]: Verifier,
  Supply-Chain Connector, Archive, Confidential Store; include KB / Bill of Materials /
  Security Signals Store.
- **D5** (gate P1 + activity cleanup): curate existing `process`/activity diagrams as
  dynamic views (no new model).

### 10.9 Defaults if a §8 decision is unanswered
Active stores → **none elevated** unless code shows an out-of-process store. AMP↔AMS →
**association**. Assurance realization → **owned by P1**.
