# REVIEW — WU-G2a Specialization Proposal

Status: applied. All 132 specializations set (7 roles, 12 events, 12 services, 13 processes, 58
functions, 31 application-components), plus the 5 missing `archimate-assignment` edges added.
Full-repo `artifact_verify`: 45/45 valid, 0 errors, 0 warnings, both before and after applying.

**Correction applied after initial pass**: the application-component inventory below originally
omitted `Bulk Delete Handler` (38 components exist; only 37 were covered) — caught during the
ledger write-up, not by the user. Added to `module` (sibling of Bulk Write Handler/Batch
Transaction Manager/Operation Registry — all four are the `archimate-assignment` performers of
`Execute Staged Bulk Operation`). Final application-component split: 6 `endpoint` / 2 `service` /
23 `module` / 7 explicitly unspecialized = 38.

## Scope

Per the user's extension of WU-G2a: evaluate every active-behavior-element entity (`process`,
`function`, `service`, `event` — plus `role`/`collaboration` for completeness) and every
`application-component` in the ENG-ARCH-REPO self-model against the specialization library in
`src/ontologies/archimate_4/specializations.yaml`, and propose which should receive a
`business-*`/`application-*`/`technology-*` (behavior/role) or `service`/`module`/`endpoint`
(application-component) specialization.

## Rubric (revised across three review rounds — see rationale below each section)

- **Processes/functions**: business vs. application is **not** about automation level or who
  triggers it — a business process can be, and often is, 100% realized by application services
  without ceasing to be business (that's what `realizes`/`serves` relationships are for). The
  actual test: does the behavior involve **real organizational/governance judgment content** —
  a decision the organization is accountable for (what to promote, how to resolve a conflict, how
  to assess conformance, how to classify a discovered element) → `business-*`; or is it **pure
  mechanism/infrastructure** with no judgment variables, existing only to make something else
  durable/consistent (staging, committing, syncing, indexing, validating against a fixed schema)
  → `application-*`. Composition/aggregation does **not** imply uniform layer across siblings —
  a business process can and typically does have some application-function children (the
  autonomous steps) and some business-function children (the authored/decided steps) at once;
  each function is judged independently on its own content, never inherited from its parent.
- **Services**: not about implementation, about **who the value is for**. Portfolio/capability
  framing recognizable to a stakeholder ("what does this give the organization?") →
  `business-service`. A concrete, interface-exposed technical operation consumed by other
  application-layer elements or backing a business process from below → `application-service`.
- **Roles**: a role played by a person or an AI agent acting *as* a person (organizational
  capacity) → `business-role`, regardless of how automated the process it performs is.
- **Application components**: `endpoint` for protocol/API adapters connecting external actors to
  the backend; `service` for components whose entire job is exposing one well-bounded callable
  capability; `module` for internal implementation units with no independent external contract;
  unspecialized for composition roots/aggregates and for components explicitly external to this
  system.

Every verdict is grounded in the entity's actual description and its real connections
(`archimate-assignment`/`archimate-composition`/`archimate-aggregation`/`archimate-realization`),
read via MCP — not inferred from name alone.

&nbsp;

## Roles (7) — all → `business-role`

`Reviewer`, `Author`, `AI Agent`, `Developer`, `Planner`, `Risk & Compliance Officer`,
`Safety / Security Analyst` — every description reads "a role performed by a human user or AI
agent when...". No exceptions; no `application-role`/`technology-role` candidates (no
component-played roles are modeled); no collaborations exist in the self-model.

&nbsp;

## Processes (13) — 9 business-process / 4 application-process

**business-process** (real judgment/governance content, regardless of automation level):
- `PRC@1776635640.U4aAdh.architecture-modelling-planning`
- `PRC@1776635645.GHVpDA.provide-implementation-guidance` (Architecture Implementation)
- `PRC@1776635649.vlE-5j.review-architecture-conformance`
- `PRC@1777293168.CYgU64.reverse-architecture`
- `PRC@1712870400.0Rz5Ex.promote-artifacts` — selecting *which* artifacts, resolving conflicts,
  verifying before publication; named a governance gate in the two-tier repository ADR.
- `PRC@1780656241.7YyhMi.manage-risk-compliance`
- `PRC@1780656241.TfWiGw.conduct-hazard-analysis`
- `PRC@1780656241.bWETd2.build-assurance-case`
- `PRC@1780656241.lXql_n.investigate-incident`

**application-process** (pure mechanism, no judgment variables):
- `PRC@1776633074.Tz_a_O.initialize-repository` — creates directory structure/config/metadata;
  deterministic provisioning, nothing to weigh or select. Its `Author`-role assignment shows who
  *triggers* the automation, not organizational judgment content — a legitimate ArchiMate pattern
  that doesn't by itself make the process business.
- `PRC@1777399926.gtgYvQ.execute-staged-bulk-operation` — assigned only by application
  components (Bulk Write Handler, Batch Transaction Manager, Bulk Delete Handler, Operation
  Registry), no role anywhere.
- `PRC@1777409515.tEdRzw.synchronize-with-remote-repository` — performed by the Git Sync Service
  component per its own description.
- `PRC@1777409610.wqtZ0P.coordinate-repository-state` — no role assignment; pure write-queue/
  index/broadcast mechanism underlying every write.

**Known gap (not blocking, recommend fixing alongside this WU)**: `Architecture Implementation`,
`Architecture Conformance Review`, and `Reverse Architecture` have no explicit
`archimate-assignment` edge despite descriptions naming human/AI performers ("human and AI
developers", "humans and AI to assess", "enabling human architects to plan"). Recommend adding
Developer→Architecture Implementation, Reviewer/AI Agent→Architecture Conformance Review, and AI
Agent→Reverse Architecture as part of applying this WU, so the business-process verdict is
backed by explicit model evidence, not just prose.

&nbsp;

## Services (12) — 2 business-service / 10 application-service

**business-service** (portfolio/capability, stakeholder-recognizable value):
`Architecture Management System` ("the whole system for managing..."), `Assurance Service`
("...within the Architecture Management System").

**application-service** (concrete, interface-exposed technical operation):
`Authoring Service`, `Verification Service`, `Discovery, Querying & Stats Service`,
`Repository Promotion Service`, `Configuration Service`, `Diagram Authoring Service`,
`Model Authoring Service`, `Model Verification Service`, `Diagram Verification Service`,
`Document Authoring Service`.

&nbsp;

## Events (12) — all → `application-event`

`Model Verification Completed`, `Repository Indexed`, `Verification Failed`,
`Artifact Write Completed`, `Artifact Write Requested`,
`Architecture Repository Change Detected`, `Artifacts Promoted`, `Promotion Plan Prepared`,
`Promotion Conflicts Detected`, `Bulk Write Requested`, `Staged Repository Committed`,
`Bulk Delete Requested`, `Workspace Conflict Detected` — every one is an internal system state
transition. No business-event candidates.

&nbsp;

## Functions (~57) — judged independently, never inherited from parent process

**business-function** (real interpretive/decision content):
`Author Model Artifacts`, `Author Diagrams`, `Author Architecture Documents`,
`Author Assurance Artifacts`, `Implement the Change` ("writes code, tests, and configuration"),
`Scope & Formulate Modelling Task`, `Plan Implementation Approach`,
`Record Implementation Decisions`, `Determine Required Changes to Architecture Content`,
`Decide Changes to Plan or Implement`, `Refine Architecture Content after Implementation`,
`Assess Implementation Against Model` (the analytical judgment step of conformance review),
`Select Artifacts for Promotion` (choosing what to promote — governance judgment),
`Resolve Promotion Conflicts` (conflict resolution — judgment, not mechanical merge),
`Map Elements to Architecture Concepts` (classification requires interpretation),
`Synthesize & Deliver Implementation Guidance` (tailoring guidance to the situation, not
templated retrieval), `Guide Assurance Method & Standards` (methodological judgment: which
standard/approach applies).

**application-function** (pure mechanism, autonomous system behavior, no judgment content):
`Attribute Schema Validation`, `Frontmatter Validation`, `Referential Integrity Check`,
`PlantUML Syntax Check`, `Frontmatter Parsing`, `Graph Traversal`, `Build Connection Graph`,
`Full-Text Search`, `Metadata Filter`, `Alias Resolution`, `Enqueue Write Commands`,
`Discover Relevant Architecture Content`, `Verify Artifact Integrity & Coherence`,
`Index Repository`, `Retrieve Architectural Context`, `Extract Architecture Baseline`,
`Report Architecture Deviations`, `Broadcast Model Update`, `Explore System Structure`,
`Check Model Coverage`, `Run Quality Gates`, `Execute Promotion`, `Detect Promotion Conflicts`,
`Validate Promotion Selection`, `Replace Promoted Entities with GRFs`,
`Resolve Operation Idempotency`, `Verify Staged Repository`, `Apply Operations to Staging`,
`Create Staging Repository`, `Commit Staged Repository`, `Check Repository Workspace Status`,
`Pull Repository Changes`, `Ingest & Reconcile Supply-Chain Signals`,
`Manage Assurance Store Lifecycle`, `Surface Modeling Gaps`, `Verify Assurance Invariants`,
`Record & Retain Tamper-Evident Assurance Evidence`,
`Validate Datatype–Data Object Relationship Consistency`,
`Resolve & Validate Datatype Attribute Types`, `Delete Assurance Analysis`,
`Compose Combined-Scope Read`.

No functions remain flagged — the judgment-content test resolves every previously-ambiguous case
cleanly (all six earlier flagged items involve real interpretation and land in
business-function).

&nbsp;

## Application components (38) — endpoint / service / module / unspecialized

**`endpoint` (6):** `Architecture MCP Endpoint Adapter`, `Architecture MCP Read Bridge`,
`Architecture MCP Write Bridge`, `Assurance MCP Endpoint Adapter`, `Assurance MCP Read Bridge`,
`Assurance MCP Write Bridge`.

**`service` (2):** `Git Sync Service`, `Identifier Allocation Service` — both focused,
single-capability, named "Service" in the self-model's own vocabulary.

**`module` (23):** `SQLite Indexer`, `Frontmatter Parser`, `Model Verifier`, `Query Engine`,
`Module Catalog`, `Promotion Engine`, `Workspace Initializer`, `Diagram Scaffolder`,
`Write Request Queue`, `PlantUML Renderer`, `Bulk Write Handler`, `Bulk Delete Handler`,
`Batch Transaction Manager`, `Operation Registry`, `Confidential Assurance Store`,
`Assurance Archive`, `Assurance Verifier`, `Supply-Chain & Vulnerability Connector`,
`Datatype Diagram Type Module`, `GSN Diagram Type Module`, `Assurance Write Queue`,
`Assurance Read Connection Pool`, `Unified Assurance Diagram Surface`.

**Unspecialized — composition roots/aggregates (4):** `Architecture Management Platform`
("active-structure root aggregating..."), `Architecture Backend` ("single runtime process...
mounting... coordinating"), `GUI Authoring Tool`, `CLI Tool` (full client applications, not
adapters/services/modules in their own right).

**Unspecialized — explicitly external to this system (3):** `AI Agent Host`, `Git Hosting`,
`Supply-Chain Signal Sources` (each description says "external").

&nbsp;

## Coverage check

7 roles + 13 processes + 12 services + 12 events + ~57 functions + 38 application-components =
139 entities assessed; every one has an explicit verdict (specialize with slug, or explicitly
left unspecialized with a stated reason). 0 collaborations exist. 0 items remain flagged after
the third review round.

## Apply plan (Step 3)

Batches of 6–10 `artifact_edit_entity` calls (setting the `specialization` field), `artifact_verify`
after each batch, per the established WU-G1b discipline. Order: roles → events → services →
processes → functions → application-components. Then add the 3 missing assignment edges
(Architecture Implementation, Architecture Conformance Review, Reverse Architecture) via
`artifact_add_connection`. Final full-repo `artifact_verify`, then tick WU-G2a in the ledger with
a progress note.
