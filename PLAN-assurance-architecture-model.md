# PLAN — Modelling the Assurance Capability in the Architecture Model

> **Scope.** Extend the self-describing ENG-ARCH-REPO model with the **architecture of the
> assurance (STPA / STPA-Sec / CAST / GRC) capability** as a new feature of the *Architecture
> Management System* — **modelling only implemented behaviour**. This is **not** an STPA/CAST/GRC
> analysis of the system (Phase 7 "dogfood", out of scope). Companion to `PLAN-assurance-stpa-grc.md`
> (the capability build plan); §N references point into that file.
>
> **Modelling rule (from review round 2):** model what is *built*. Planned-but-unbuilt extensions
> (e.g. further store adapters) are described as **extension points on a boundary component**, not as
> target-state entities.
>
> **Status:** drafted 2026-06-05; revised after two review rounds. Granularity confirmed (one Assurance
> Service + processes). Build order: **motivation first → confirm → business/common → application →
> technology → diagrams → save**.

> ⚠️ **SUPERSEDED on assurance runtime topology (2026-06-06).** The "**one Assurance MCP
> Server** + **one Assurance MCP Interface**" decisions in this plan (rows §1.3, §216/§227,
> and the connection table §299–§304) are **superseded** by `PLAN-backend-runtime-
> unification.md` and `PLAN-c4-self-model-narrative.md`. Target instead:
> **assurance MCP is mounted in `arch-backend`** (`/mcp/assurance-read` + `/mcp/assurance-
> write`, gated); the runtime surfaces are **two stdio bridges** (assurance read/write) +
> their **two distinct stdio interfaces**; the former *Assurance MCP Server* entity is
> **reframed as a Backend-internal "Assurance MCP Endpoint Adapter"** (aggregated by the
> backend, not a separate server/container); and the assurance components form an
> **`Assurance Module` concern grouping** (not a deployment boundary). The
> `Assurance Service` is realized by **functions/processes**, not by a component. Apply
> these when executing the unification work.

## 0. Framing & anchoring

The existing model is the architecture of the **Architecture Management System** (a `common` `service`
aggregating Authoring / Verification / Discovery / Promotion / Configuration services, realised by
application components over SQLite/Git/Python/PlantUML). Assurance is a **major new capability of that
same system**, anchored into the existing graph so it reads as one narrative:

- `Architecture Management System` → `aggregation` → `Assurance Service`.
- assurance processes → `realization` → `Assurance Service` → `realization` → assurance components
  (mirrors `Architecture Modelling & Planning → Authoring Service → MCP Model Server`).
- `Verify Assurance Invariants` → `realization` → existing `Verification Service`.
- `Manage Assurance Store Lifecycle` → `association` → existing `Configuration Service`.
- Assurance authoring/diagram/document behaviour reuses the existing GUI Authoring Tool, CLI Tool,
  Diagram Authoring Service, Document Authoring Service (extended, not duplicated).
- Requirement *Assurance as a Separate Module Family* → `association` → existing principle
  `Extensibility and Configurability`.
- Throughput motivation ties to the existing agentic-velocity narrative (`AI-Assisted Development as
  Dominant Production Mode`; `Achieve Unity of Effort Across Autonomous, Agentic SDLC Work`).

**Do NOT model:** `loss`/`hazard`/`UCA`/`constraint`/`risk`/`obligation` *instances* (Phase 7); any
entity per MCP-tool, per skill-script, or per verifier-rule; unbuilt adapters (PostgreSQL/Supabase) as
entities; any ADR/specification documents this pass.

## 1. Review resolutions

**Round 1** (kept): removed the factually-wrong "compliance records can't be bolted on later"
assessment; reframed the traceability assessment to the *silo* not the document; dropped "Live" from
the headline goal; reframed non-expert motivation **positively** (friction/throughput, *supporting*
experts — never "fewer experts"); requirements 9→7; included assurance-case building; specialized
`Assurance Analysis`; added `Assurance Audit Record`; renamed the connector; one Assurance MCP
Interface; granular data-objects over one blob; `Classification Reference Catalog`; no ADRs.

**Round 2** (this revision — all verified against `src/`):

| # | Concern | Resolution |
|---|---|---|
| 1 | Entities/descriptions exceed implemented functionality | **Model only built capability.** Verified: PostgreSQL/Supabase **not implemented** → removed. private-git **now has an encrypted adapter** (`EncryptedPrivateGitAssuranceStore`, Fernet/AES, decrypt-on-load; selectable via `store_backend: private-git` + key in OS keychain) — the plain adapter also remains as an unencrypted option. Baselines are **hash-anchored, not signed**; RFC 3161 is **opt-in**. Connector does ingest/map/list/export/reconcile — **no automated exposure/loss contextualisation** (that emerges from graph linkage). Wording tightened throughout. Future adapters live in the store boundary description. |
| 2 | Persistence topology = three stores, two trust zones | **Adopted** (§4.1). Confidential SQLCipher `store.db` holds the knowledge base **and** the audit-log + baseline tables (same DB, same key); the security-signals SQLite DB is **separate and unencrypted**. `AssuranceArchive` is a separate *port/responsibility*, not a separate physical store. |
| 3 | Lifecycle / UI / output under-modelled | **Added** `Manage Assurance Store Lifecycle` function (assoc. Configuration Service); connect assurance to existing GUI/CLI/Diagram/Document authoring; **one** Assurance MCP Server + **one** Assurance MCP Interface (description notes the read/write scoped surfaces). |
| 4 | Regulatory motivation should be durable + non-advisory | Driver → **Expanding Software & AI Assurance Obligations**; assessment → **Affected Teams Need Traceable & Tamper-Evident Assurance Records**. No dates/retention periods in entities (examples in notes); applicability/compliance are explicitly **human** judgements. |
| 5 | Connection design under-specified | **Added a connection inventory** (§6), grounded in verified existing conventions. |
| 6 | `Assurance Graph` → `Assurance Knowledge Base` | **Renamed.** Store-wide shared resource (analyses + registers + references + records); **accessed** by store/verifier/MCP/functions; does **not** realize one analysis (matches `SQLite Index`, which is access-only). Business-objects are produced by their processes. No per-analysis data-objects. |
| 7 | Skills/guidance need one coherent abstraction — for **both** general & assurance work | **One** `Assurance Method Guidance` data-object (not four skills), accessed by `Guide Assurance Method & Standards` + MCP read behaviour. **Plus** a parallel general-architecture improvement: a new `Architecture Modelling Guidance` data-object (§3.1) closing the same gap for general work. Guidance behaviour/interface serves the roles — the AI Agent role is **not** wired directly to the data-object. |
| 8 | Diagrams = narrower viewpoints | **4 ArchiMate diagrams + 1 matrix** (§5). |
| 9 | Footprint recount | ≈ **58–60** (§7), honest with trim levers. |

### 1.1 Design findings (from the round-2 investigation — these concern `PLAN-assurance-stpa-grc.md`, not just the model)

- **Store adapters: SQLCipher (encrypted, default), PocketBase, private-git (plain JSON or encrypted).**
  An encrypted private-git adapter (`EncryptedPrivateGitAssuranceStore`) is now **built** — Fernet
  encryption at rest, decrypt-on-load so queryability is preserved (the in-memory read model is the
  only query surface; on-disk files are ciphertext). Selected via `store_backend: private-git`; key in
  OS keychain (reuses `arch-assurance` service). The plain private-git adapter remains for teams whose
  git repo ACLs are the confidentiality boundary. Supabase/Postgres remains planned-but-unbuilt →
  not modelled. `PLAN-assurance-storage-confidentiality.md` §SC-3 closed.
- **Separate security-signals store is sound.** Different concern (reference *inputs* vs the analysis
  graph), lifecycle (high-volume, CI-re-ingested), reachability (§27.1). Keep it separate. All three
  persistence concerns are already **port-based** (`ConfidentialAssuranceStore`, `AssuranceArchive`/
  `WORMAssuranceArchive`, `SecuritySignalConnector`), so the requested pluggability exists at port level.
- **Signals confidentiality — corrected and recorded.** An SBOM of *our* system **is confidential**: it
  captures the root component (our system/service name + version), the full dependency composition, the
  vulnerabilities of those components, and the anchor mappings to our **named architecture entities** — an
  attack-surface map. The implementation's "BOM component lists are generally not sensitive" is rejected
  (it holds only for the generic public CVE/PURL *catalog* = the §4.1 reference vocabulary, modelled
  separately as `Classification Reference Catalog`). **Decision in `PLAN-assurance-stpa-grc.md` §27.4:**
  signals confidential by default + TLP + minimisation; signals store pluggable with an encrypted/
  co-located adapter (the plain-SQLite adapter is the *public-BOM* path only).

---

## 2. Motivation domain (build first)

**Stakeholders (+2):** Safety / Security Analyst; Risk & Compliance Officer. *(Non-expert ≈ existing
Developer / Product Owner; model-owner ≈ Architect.)*

**Drivers (+2, external):**

| Name | Summary |
|---|---|
| Expanding Software & AI Assurance Obligations | A durable external trend toward greater safety/security/assurance and evidence expectations for software and AI, reaching small teams. *(Notes: illustrative, jurisdiction-dependent examples — EU AI Act, Cyber Resilience Act, sector standards — not legal advice; applicability is a human judgement.)* |
| Safety, Security & GRC Capability Gap for Small Teams | Personal projects and SMBs lack dedicated assurance tooling *and* method/legal expertise. |

Also reuse existing driver **AI-Assisted Development as Dominant Production Mode** for the throughput
assessment.

**Assessments (+3):**

| Name | From → motivates |
|---|---|
| Assurance Disconnected From Architecture Loses Traceability | obligations + capability-gap → siloed assurance loses the loss→hazard→control→evidence chain → *first-class assurance over the model* goal. |
| Affected Teams Need Traceable & Tamper-Evident Assurance Records | obligations driver → teams subject to these obligations must produce traceable, tamper-evident, retained records → *Tamper-Evident Assurance Records* requirement. |
| Assurance Cannot Keep Pace with Agentic Development Velocity | AI-velocity + capability-gap → expert-bottlenecked, high-friction assurance becomes the constraint; without lowering friction and *supporting* experts, assurance falls behind and unity of effort breaks. |

**Goals (+2):**

| Name | Summary |
|---|---|
| Provide First-Class Assurance over the Architecture Model | Safety, security and GRC analysis as a reusable capability cross-referenced to the same model, so the assurance chain is one queryable, traceable graph. |
| Lower the Barrier to Rigorous Assurance Work | Reduce method/legal friction and barrier-to-entry, and speed up and *support* assurance, so it keeps pace with agentic development and experts spend less effort per analysis (**not** fewer experts). → `influence` existing `Achieve Unity of Effort…`. |

**Outcomes (+3):** Assurance Findings Traceable End-to-End to the Architecture Model · Assurance
Analysis Surfaces Modeling Gaps · Assurance Friction & Guidance Overhead Reduced.

**Principles (+2):** Safety Is Never Subordinate to Risk (§2.1) · Assurance Content Is Confidential by
Default (TLP, encrypted tier, one-way `assurance→architecture` refs).

**Requirements (+7):**

1. **Assurance as a Separate Module Family** — `module_class: assurance`; gated MCP servers; its own
   constraint-centric ontology, excluded from model views; generic components branch declaratively.
   → `association` to *Extensibility and Configurability*.
2. **Pluggable, Confidential Assurance Storage** — *all* assurance persistence — the knowledge base,
   the tamper-evident audit log/archive, **and** the security-signals store — is accessed via **ports
   with swappable adapters** (store: SQLCipher default / PocketBase / private-git plain or encrypted;
   archive: in-store / WORM; signals: SQLCipher-colocated default / SQLite public-BOM opt-out), so
   backend **and confidentiality posture are per-deployment choices** — mirroring the general
   read-model's pluggable storage. Encrypted-at-rest by default via SQLCipher; fail-closed gated;
   OS-keychain key; all signals carry TLP (default `TLP:AMBER`). → `association` to *Extensibility and
   Configurability*. *(Realization gap closed: `sqlcipher-colocated` signals adapter shipped as the
   default in `PLAN-assurance-storage-confidentiality.md` §SC-1/SC-2.)*
3. **Tamper-Evident Assurance Records** — append-only, hash-chained audit log + sealable
   hash-anchored baselines + optional RFC 3161 timestamping + configurable retention. *(Stronger WORM
   immutability / legal-hold / crypto-shred are opt-in, regulated-tier — not the default.)*
4. **Assurance↔Architecture Linkage** — optional bindings for traceability; references persisted
   **one-way** (`assurance→architecture`); back-navigation computed, never persisted.
5. **Guidance-First Assurance Method Support** — `assurance_guidance`, method skills, teaching
   verifier messages, document templates; ask-don't-assume for safety/security/legal judgements.
6. **Assurance Method-Completion Verification** — hard structural validity + the safety-disposition
   safeguard + opt-in method-completion profiles.
7. **External Supply-Chain Signal Ingestion** — ingest SBOM / vulnerability feeds / AI-BOM, map to
   architecture components, and round-trip/reconcile the AI-BOM. *(The actionable architectural + loss
   context emerges from linking mapped components into the assurance graph; it is not computed by the
   connector.)*

*Chain:* drivers `→influence→` assessments `→association→` goals; outcomes `→realization→` goals;
requirements `→realization→` outcomes (or `→influence→` goals directly); requirements `→association→`
principles (req 6 ↔ safety; reqs 2/3/4 ↔ confidentiality).

---

## 3. Business & common domain

**Service (+1):** **Assurance Service** — `aggregation`-from `Architecture Management System`. Safety,
security and GRC analysis over the architecture model, gated behind the confidential tier.

**Processes (+4)** — each produces one analysis artifact (1:1 with the business-objects):

| Process | Produces |
|---|---|
| Conduct Hazard Analysis | STPA Analysis (STPA-Sec via `concern_class`) |
| Investigate Incident | CAST Investigation |
| Manage Risk & Compliance | GRC Assessment |
| Build Assurance Case | Assurance Case |

**Functions (+7):**

| Function | Body |
|---|---|
| Author Assurance Artifacts | Create/edit assurance entities + one-way connections via the gated MCP tools, write-scoped. |
| Verify Assurance Invariants | Hard structural validity + safety-disposition safeguard + opt-in completion profiles; `realizes` the existing Verification Service. |
| Guide Assurance Method & Standards | Step-level method coaching (intent / when / why) + standards/legal *pointers* (illustrative, non-advisory) via `assurance_guidance`, teaching verifier messages, templates; ask-don't-assume. Reads `Assurance Method Guidance` (§4). |
| Surface Modeling Gaps | Detect assurance nodes/UCAs/scenarios not bindable to an architecture entity (`binding_status ∈ {unbound-pending, out-of-scope}`); emit `modeling-gap` findings + the guided "model this" action (§7.1). |
| Record & Retain Tamper-Evident Assurance Evidence | Append every mutation to the hash-chained audit log at write time; seal a hash-anchored baseline at sign-off (optional RFC 3161 timestamp); enforce retention + integrity verification. *(WORM/crypto-shred is opt-in.)* |
| Ingest & Reconcile Supply-Chain Signals | Ingest SBOM (CycloneDX/SPDX) → map to architecture components; ingest vulnerability feeds (OSV/NVD/GHSA/CISA-KEV, +VEX) → attach to mapped components; emit + reconcile the AI-BOM (drift report). |
| Manage Assurance Store Lifecycle | Initialise / unlock / status / backup / export / rotate-key + recovery-key export for the confidential store; fail-closed gating. → `association` existing **Configuration Service**. |

**Roles (+2, common):** Safety / Security Analyst, Risk & Compliance Officer — `assignment` to the
relevant processes/functions (the existing AI Agent role is also assigned, per the model's
`Human Author or AI Agent` junction pattern). No new business-actors.

**Business-objects (+7):** `Assurance Analysis` (general) with `specialization`s **STPA Analysis /
CAST Investigation / GRC Assessment / Assurance Case**; **Assurance Audit Record** (tamper-evident
record); **Confidential Assurance Repository** (the third tier — parallels Enterprise/Engagement
Repository). Processes `access` (produce) their respective business-object.

### 3.1 General-architecture guidance improvement (concern 7, both sides)

Today the model represents *general* guidance only as behaviour (`Synthesize & Deliver Implementation
Guidance`, `Retrieve Architectural Context`), an outcome (`Architectural Guidance Available Without
Specialist Dependency`), and raw config (`Architecture Ontology Configuration` + the `*-Type
Definition` business-objects). The **guidance content itself is unmodelled.** Close the gap on both
sides with one passive-structure resource each:

- **(general, +1 data-object)** `Architecture Modelling Guidance` — the machine-consumable guidance
  the system provides: the authoring-guidance catalog (type create-when/never-create, permitted
  connections, domain reference models) and the `archimate-modelling` + `reverse-architecture` skill
  directories. `accessed` by `Synthesize & Deliver Implementation Guidance` / `Retrieve Architectural
  Context`; `association` with `Architecture Ontology Configuration` (derived from it); supports the
  existing `Architectural Guidance Available…` outcome.
- **(assurance, the §4 data-object)** `Assurance Method Guidance` — the STPA/CAST/GRC/assurance-case
  skill directories + `assurance_guidance` content; `accessed` by `Guide Assurance Method & Standards`.

Both are *resources accessed by guidance behaviour*; the behaviour/interface serves the consumer roles
(no role→data-object edge). Future skills are listed in the data-object body, not added as entities.

---

## 4. Application domain

**Components (+5):** Assurance MCP Server (one server; description notes: read/write scoped tool
surfaces; configurable TLP max-classification ceiling — artifacts above the ceiling are withheld and
the attempt is logged, enforcing the *Assurance Content Is Confidential by Default* principle at the
AI boundary) · Confidential Assurance Store (pluggable port; SQLCipher default) · Assurance Archive
(append-only hash-chained log + baselines — a separate *responsibility*, same physical SQLCipher DB) ·
Assurance Verifier (`Model Verifier` parallel; safety safeguard + profiles) · Supply-Chain &
Vulnerability Connector (SBOM/vuln/AI-BOM ingest, map, export, reconcile; signals gated behind
store-unlock when confidential backend is active).

> `module_class` / enablement / `/api/modules` is an **edit to the existing Model Registry** + bootstrap.

**Application interface (+1):** **Assurance MCP Interface** — one interface; its description states the
implementation exposes separately-scoped read and write tool surfaces (modelling them as two interfaces
would add no architectural insight). REST/CLI/Web reused.

**Data-objects (+7):**

| Data-object | Note |
|---|---|
| Assurance Knowledge Base | Store-wide confidential resource: assurance entities + typed one-way connections + registers + references. **Accessed** (not realized) by the store, verifier, MCP server, and authoring/verify/ingest functions — the analog of `SQLite Index`, which is access-only. Does not realize a single analysis. |
| Assurance Audit Log | Append-only hash-chained log + sealed baselines; `realizes` `Assurance Audit Record`. |
| Security Signals Store | SBOM components + vulnerabilities + anchor mappings (the separate, **unencrypted** signals DB). |
| Bill of Materials | External interchange artifact ingested (SBOM) and emitted (AI-BOM), CycloneDX/SPDX. |
| Classification Reference Catalog | Versioned STRIDE/CWE/ATT&CK/CVE + obligation-catalog data, validated against (§4.1) — taxonomies as data, not code. |
| Assurance Method Guidance | One resource = the 4 assurance skill directories + `assurance_guidance` content (§3.1). |
| Architecture Modelling Guidance | **General-architecture** guidance resource (§3.1) — authoring-guidance catalog + general skills. |

### 4.1 Persistence topology & trust boundaries (concern 2)

```
┌─ confidential, ENCRYPTED (SQLCipher, one key, OS keychain) ──────────────┐
│  Encrypted Assurance Database  (.arch-assurance/store.db)                 │
│    ├─ realizes → Assurance Knowledge Base   ← accessed by Confidential    │
│    │                                          Assurance Store, Verifier,  │
│    │                                          MCP Server                  │
│    ├─ realizes → Assurance Audit Log        ← accessed by Assurance       │
│    │             (audit-log + baseline tables, same DB/key)   Archive     │
│    └─ realizes → Security Signals Store     ← accessed by Supply-Chain &  │
│                  (co-located signals tables, same DB/key — DEFAULT)         Vulnerability Connector
└──────────────────────────────────────────────────────────────────────────┘
┌─ CONFIDENTIAL data; plain-SQLite opt-out path ────────────────────────────┐
│  Security Signals Database  (.arch-assurance/security-signals.db)          │
│    signals_backend: sqlite  → opt-in for deployments where BOM data is     │
│    intentionally public (e.g. open-source project public SBOM disclosure)   │
└──────────────────────────────────────────────────────────────────────────┘
   one-way refs: Assurance Knowledge Base ─→ architecture entities (never reverse)
   existing architecture SQLite Index stays separate (not the assurance source of truth)
```

All three concerns are reached through **pluggable ports** (`ConfidentialAssuranceStore`,
`AssuranceArchive`, `SecuritySignalConnector`). The **default** since `PLAN-assurance-storage-confidentiality.md`
§SC-2: signals are co-located in `store.db` (encrypted, TLP:AMBER by default). The plain-SQLite
`Security Signals Database` is the **explicit public-BOM opt-out** path (`signals_backend: sqlite`),
not the default. `Security Signals Store` remains a separate data-object port regardless of adapter.

---

## 5. Technology domain (implemented store backends only)

| Type | Name | Note |
|---|---|---|
| system-software | SQLCipher | Default embedded, encrypted backend (`store.db`). |
| system-software | PocketBase | Self-hosted RBAC backend (teams). |
| system-software | OS Keychain | Auto-managed encryption key + recovery export. |
| artifact | Encrypted Assurance Database | `store.db` — `realizes` Assurance Knowledge Base **and** Assurance Audit Log. |
| artifact | Security Signals Database | `security-signals.db` — plain SQLite, the **public-BOM opt-out path** (`signals_backend: sqlite`). The default since §SC-2 is co-located in `store.db` (encrypted). `realizes` Security Signals Store when this path is active. |
| *(reuse)* | Git VCS | **private-git** backend. Two adapters: plain JSON (`PrivateGitAssuranceStore`, unencrypted — for deployments relying on repo ACLs) and Fernet-encrypted (`EncryptedPrivateGitAssuranceStore`, AES-128-CBC+HMAC, decrypt-on-load). Selected via `store_backend: private-git`; key in OS keychain. |

Backends `→serving→` the relevant assurance port (store / archive / signals). **Unbuilt adapters
(PostgreSQL/Supabase; an encrypted signals adapter) are NOT modelled** — described as extension points
on the respective port components (the pluggability is the modelled invariant; specific future adapters
are not). Hosted on existing `Developer Workstation`. External feeds/tools (OSV, NVD, GitHub Advisory,
Dependency-Track, runtime AI-discovery) referenced in bodies, not modelled.

---

## 6. Connection inventory (concern 5 — grounded in verified conventions)

| Source | Relationship | Target | Rationale |
|---|---|---|---|
| Architecture Management System | aggregation | Assurance Service | assurance is part of the whole system |
| each assurance process | realization | Assurance Service | processes realise the offered service (cf. `Architecture Modelling & Planning → Authoring Service`) |
| Assurance Service | realization | each assurance component | service realised into components (cf. `Authoring Service → MCP Model Server`) |
| Assurance Service | serving | Assurance MCP Interface | service offered via the interface (cf. `Authoring Service → MCP Interface`) |
| each process | aggregation | the functions it uses | process aggregates functions (cf. `… → Author Model Artifacts`) |
| Safety/Security Analyst, Risk & Compliance Officer, AI Agent | assignment | relevant processes/functions | active structure performs behaviour (cf. `Human Author or AI Agent → Author Model Artifacts`) |
| Assurance MCP Server | assignment | Assurance MCP Interface | component exposes the interface |
| Confidential Assurance Store | access | Assurance Knowledge Base | store reads/writes the graph |
| Assurance Verifier, Assurance MCP Server | access | Assurance Knowledge Base | verify / query |
| Assurance Archive | access | Assurance Audit Log | append-only log + baselines |
| Supply-Chain & Vulnerability Connector | access | Security Signals Store, Bill of Materials | ingest/map/export/reconcile |
| Guide Assurance Method & Standards | access | Assurance Method Guidance | guidance behaviour reads the resource |
| Verify Assurance Invariants | realization | Verification Service (existing) | extends existing verification |
| Manage Assurance Store Lifecycle | association | Configuration Service (existing) | lifecycle is a configuration responsibility |
| Encrypted Assurance Database | realization | Assurance Knowledge Base, Assurance Audit Log | one SQLCipher file backs both |
| Security Signals Database | realization | Security Signals Store | separate unencrypted SQLite |
| SQLCipher / PocketBase / Git VCS | serving | Confidential Assurance Store | backends serve the store port |
| OS Keychain | serving | Confidential Assurance Store | provides the encryption key |
| Assurance Knowledge Base | (one-way ref) | architecture entities | optional bindings, never reverse-persisted |

*Exact permitted relationship/direction for each is confirmed via `artifact_authoring_guidance` +
dry-run at build (the model is authority for its own conventions).*

---

## 7. Diagrams, documents, footprint & sequencing

**Diagrams (4 ArchiMate + 1 matrix), narrow viewpoints:**

| # | Diagram | Scope (≈ elements) |
|---|---|---|
| 1 | Why Assurance | durable motivation: drivers → assessments → goals → outcomes (~10–12) |
| 2 | Assurance Methods & Roles | Assurance Service → 4 processes → 2 roles → 4 analysis outputs |
| 3 | Assurance Application Architecture | 7 functions → 5 components → Assurance MCP Interface → knowledge/guidance data-objects |
| 4 | Assurance Persistence & Trust Boundaries | store/archive/connector → 3 data-objects → 2 DB artifacts + keychain; encrypted vs unencrypted zones; one-way ref to the model |
| M | Assurance Requirements Traceability | matrix: 7 requirements × realising services/components (+ principle associations) |

**Documents:** none (no ADRs). New doc-/diagram-type *definitions* are config; model as `Document/
Diagram Type Definition` business-objects only later if wanted.

**Footprint (recounted):** motivation 21 · common/business 21 · application 13 (incl. +1 general
guidance) · technology 5 ≈ **60** new entities (+ connections), vs 242 existing. Trim levers: fold
`Bill of Materials` into `Security Signals Store`; drop the `Assurance Case` specialization+process;
the general `Architecture Modelling Guidance` is a separable improvement.

**Build order:** (1) Motivation — build + `artifact_verify` + show, **confirm before continuing**.
(2) Business/common (incl. §3.1 general-guidance improvement). (3) Application + persistence topology.
(4) Technology. (5) Diagrams + matrix. (6) Repo-wide verify + save. Batches via `artifact_bulk_write`,
dry-run first; every connection checked against the graph + authoring-guidance before commit.
