# Composition Classification Spike (WU-G1a / WU-G1b)

**Status: applied.** User approved this rubric and review list; the 86 approved conversions
below were executed via `artifact_edit_connection`(remove)+`artifact_add_connection`(add) and
verified (see ledger 2026-07-12 WU-G1b entry for the final count-based cross-check: 69
aggregation + 86 composition = 155). The 17 motivation-layer edges were left unconverted per
explicit user instruction; the ~45 mechanically-shared edges correctly stay aggregation. This
document is kept as the historical record of the rubric, the two corrections, and the full
per-source review list — not re-editable after the fact.

This was the review packet for WU-G1a: a classification rubric for the self-model's 155
`archimate-aggregation` connections, plus a reviewed sample applying it.

## Rubric

A currently-`archimate-aggregation` connection converts to `archimate-composition` only if
**both** hold:

1. **Existence-dependent**: the target has no existence outside its containment by this
   specific source, *as the model currently represents it* — deleting the source would
   delete the target with it, not leave it standing alone or reassignable to something else.
2. **Exclusive**: the target is not also referenced (via the same or a different
   aggregation/composition edge) from any other source in the model. A part shared across
   more than one whole cannot be exclusively composed into either.

**Correction (2026-07-12, after user review) — what does NOT defeat existence-dependence:**
an earlier pass through this rubric wrongly treated two things as proof of aggregation that
are not:

- **Hypothetical extractability.** "You could pull this module out with some engineering
  work and give it independent existence" is true of almost any well-factored software
  component and proves nothing about the *current* model. The test is whether the part is
  presently, actually a constituent of the whole — not whether some future refactor could
  change that.
- **Runtime optionality/configurability.** A module gated by a feature flag (present in the
  codebase, compiled/shipped as part of the one system, just conditionally *active*) is
  still structurally a constituent. Composition is about structural containment, not about
  whether the part happens to be switched on. "It's opt-in" answers a different question
  than "does it exist independent of this system."

Consequence: for a software module (an `application-component`/`data-object` etc. that is
literally a source-code directory or class inside *this one codebase*), "existence-dependent"
should be read as: **does this thing exist as a deployable, meaningful artifact outside the
build/runtime of this specific containing system?** If the answer is no — it is source code
that only exists because this project exists, and would cease to exist as a functioning thing
if this project's tree were deleted — that satisfies leg 1, regardless of feature flags or
in-principle extractability. A genuinely different runtime host (e.g. a standalone process
that some *other* composition root also starts and that can run without this source) is what
actually defeats exclusivity/existence-dependence — not merely "a human could factor this out
some day."

This correction changes verdicts #1, #6, and (after a second correction — see #7 below) #7
from an earlier aggregation-by-default read of "catalog/grouping," "optional module," and an
unverified process-topology claim into composition. It does **not** change verdicts that rest
on genuine sharing: the same target reachable from ≥2 sources *within the model itself*. That
signal is model-internal and mechanical — it doesn't depend on any claim about how the system
actually runs, so it isn't exposed to the kind of error #1/#6/#7 made.

Practical signal used below, and now computed across the full 155 (see "Full-list mechanical
split" below): if the *same target artifact id* appears as the target of more than one
aggregation edge anywhere in the 155-list, that alone is sufficient to classify it as
shared-membership aggregation, without needing to read its content. For single-occurrence
(exclusive) pairs, read the target's own description, but do not stop at "is this
optional/pluggable" or infer process topology from a grep/list-membership — read the actual
governing file or ADR if a process-topology claim is going to do real work in the verdict (the
#7 correction below is the cautionary example of skipping this).

## Method

Queried the self-model via `arch-repo-read` MCP tools (`artifact_query_list_artifacts`,
`artifact_query_find_connections_for`, `artifact_query_read_artifact`). Confirmed the known
count: 155 `archimate-aggregation` connections, distributed across projects/groups as:

| group | count |
|---|---|
| platform-core | 95 |
| assurance | 23 |
| motivation-narrative | 20 |
| promotion-and-tiering | 16 |
| diagram-authoring | 1 |

Sampled 20 connections spanning all five groups, favoring pairs whose source or target
recurs elsewhere in the 155-list (to test the shared-membership signal directly) plus a few
single-occurrence pairs (the only candidates the rubric could plausibly convert).

## Full-list mechanical split (all 155, not just the sample) — and a script bug caught along the way

The user asked directly whether the 135 non-sampled connections need re-evaluation too — yes,
and unlike the qualitative verdicts above, this part is a mechanical count over the full
155-list (every target's occurrence count), not an inference, so it's not exposed to the same
kind of error. **But my first attempt at even this mechanical count had a real bug**: one
entity's own id slug ends in `-` (`DOB@1777239299.LeI0v-`), and splitting the connection id on
the literal substring `---` landed one character short of the true boundary for that entity's
edges, silently mis-keying two of its targets under phantom ids no other edge used — which made
them look artificially exclusive. Caught by re-deriving the split with a check (target must not
start with a stray `-`) and re-running; the true count is:

| group | total | exclusive target (single occurrence) | shared target (≥2 sources) |
|---|---|---|---|
| platform-core | 95 | 77 | 18 |
| assurance | 23 | 9 | 14 |
| motivation-narrative | 20 | 17 | 3 |
| promotion-and-tiering | 16 | 7 | 9 |
| diagram-authoring | 1 | 0 | 1 |
| **total** | **155** | **110 (71%)** | **45 (29%)** |

(This is a small, contained correction — 3 edges moved from "exclusive" to "shared" — and this
is the kind of mechanical check I should be running proactively, not just when asked.)

The 45 shared-target edges are mechanically aggregation. The 110 exclusive-target edges are the
full WU-G1b review list below — every one read and classified, not projected from the sample.

## Full WU-G1b review list (all 110 exclusive-target edges, by source)

Fetched every exclusive-target edge's source/target names via `artifact_query_find_connections_for`
(31 distinct sources cover all 110 edges). Three categories, per the twice-corrected rubric:

- **Composition** — an internal software/behavioral constituent of this one system with no
  independent existence outside it (source code, a process's own sub-function, a service's own
  sub-service, a data structure specific to one subsystem).
- **Aggregation — portable/generic technology** — genuinely independent existence confirmed:
  the target is redeployable or a widely-used third-party tool, not authored by/exclusive to this
  project (the *actual* test that #6/#7 initially got wrong by using the wrong reasoning; this
  case passes it for a real reason).
- **Aggregation — motivation-layer, OPEN QUESTION** — REQ/GOL decomposition; deferred pending
  your view (see "Open question" above), left unconverted either way.

| Source | Targets (count) | Category | Verdict |
|---|---|---|---|
| Architecture Backend (`APP@…OYEmP1`) | SQLite Indexer, Frontmatter Parser, Model Verifier, Architecture MCP Endpoint Adapter, Query Engine, Module Catalog, Promotion Engine, Workspace Initializer, Diagram Scaffolder, Write Request Queue, Git Sync Service, PlantUML Renderer, Bulk Write Handler, Batch Transaction Manager, Bulk Delete Handler, Operation Registry, Assurance MCP Endpoint Adapter, Assurance Write Queue, Assurance Read Connection Pool, Unified Assurance Diagram Surface (20) | composition | **convert** (20) |
| Architecture Management Platform (`APP@…hkrdtm`) | Architecture Backend, CLI Tool, GUI Authoring Tool, Architecture MCP Read Bridge, Architecture MCP Write Bridge, Assurance MCP Read Bridge, Assurance MCP Write Bridge, Assurance Module (8) | composition | **convert** (8) |
| Assurance Module (`GRP@…rW_2nX`) | Confidential Assurance Store, Assurance Archive, Assurance Verifier, Supply-Chain & Vulnerability Connector, Assurance Knowledge Base, Bill of Materials, Security Signals Store (7) | composition | **convert** (7) |
| Promote Artifacts (`PRC@…0Rz5Ex`) | Run Quality Gates, Execute Promotion, Select Artifacts for Promotion, Detect Promotion Conflicts, Validate Promotion Selection, Resolve Promotion Conflicts, Replace Promoted Entities with GRFs (7) | composition (process→own sub-function) | **convert** (7) |
| Architecture Management System (`SRV@…fu8ZS1`) | Authoring Service, Verification Service, Discovery/Querying & Stats Service, Repository Promotion Service, Configuration Service, Assurance Service (6) | composition (service→own sub-service) | **convert** (6) |
| Architecture Implementation (`PRC@…GHVpDA`) | Synthesize & Deliver Implementation Guidance, Implement the Change, Record Implementation Decisions, Plan Implementation Approach, Refine Architecture Content after Implementation (5) | composition | **convert** (5) |
| Execute Staged Bulk Operation (`PRC@…gtgYvQ`) | Resolve Operation Idempotency, Verify Staged Repository, Apply Operations to Staging, Create Staging Repository, Commit Staged Repository (5) | composition | **convert** (5) |
| Coordinate Repository State (`PRC@…wqtZ0P`) | Enqueue Write Commands, Index Repository, Broadcast Model Update, Compose Combined-Scope Read (4) | composition | **convert** (4) |
| Discover Relevant Architecture Content (`FNC@…lLdx12`) | Graph Traversal, Full-Text Search, Metadata Filter (3) | composition | **convert** (3) |
| Architecture Conformance Review (`PRC@…vlE-5j`) | Extract Architecture Baseline, Assess Implementation Against Model, Report Architecture Deviations (3) | composition | **convert** (3) |
| Reverse Architecture (`PRC@…CYgU64`) | Explore System Structure, Map Elements to Architecture Concepts, Check Model Coverage (3) | composition | **convert** (3) |
| Module Catalog (`APP@…yNhgdh`) | Datatype Diagram Type Module, GSN Diagram Type Module (2) | composition (own plugin modules) | **convert** (2) |
| Index Repository (`FNC@…dxb6ru`) | Build Connection Graph, Alias Resolution (2) | composition | **convert** (2) |
| Architecture Modelling & Planning (`PRC@…U4aAdh`) | Scope & Formulate Modelling Task, Decide Changes to Plan or Implement (2) | composition | **convert** (2) |
| Synchronize With Remote Repository (`PRC@…tEdRzw`) | Check Repository Workspace Status, Pull Repository Changes (2) | composition | **convert** (2) |
| Diagram (`BOB@…eGCeZq`) | Rendered Diagram Representation (1) | composition (rendering only exists as a rendering of the diagram) | **convert** (1) |
| Datatype Diagram (`BOB@…dMbHkg`) | Classifier (1) | composition — already #10 above | **convert** (1) |
| Canonical Per-Repo Artifact Index (`DOB@…4f-C9z`) | SQLite Index (1) | composition — verified: SQLite Index's own description reads *"a derived, disposable artifact — always regenerable from the source files in the repository"*, this system's own runtime index data structure, not the generic SQLite technology (that's the separate `ART`/`SSW` pair under Developer Workstation) | **convert** (1) |
| Referential Integrity Check (`FNC@…eAkU8w`) | Resolve & Validate Datatype Attribute Types (1) | composition | **convert** (1) |
| Verify Artifact Integrity & Coherence (`FNC@…NGjUCa`) | PlantUML Syntax Check (1) | composition (NGjUCa is shared as a *target* elsewhere — that's unaffected; this is its own outbound edge) | **convert** (1) |
| Conduct Hazard Analysis (`PRC@…TfWiGw`) | Surface Modeling Gaps (1) | composition | **convert** (1) |
| Build Assurance Case (`PRC@…bWETd2`) | Record & Retain Tamper-Evident Assurance Evidence (1) | composition | **convert** (1) |
| Developer Workstation (`NOD@…4EFX7z`) | SQLite Database, Git Repository, Git VCS, Python Runtime, PlantUML Engine, OS Keychain, SQLCipher (7) | **aggregation — portable/generic** | **no change** (7) — genuinely independent existence: Python/Git/PlantUML/SQLCipher are third-party tools that exist and are reusable regardless of this project; the artifact/database instances are themselves redeployable to a different node without ceasing to be meaningful. Deletion test passes in the *aggregation* direction here, unlike the software-module cases above. |
| Achieve Unity of Effort (`GOL@…FCfDuc`) | 4 sub-goals | aggregation — motivation, OPEN QUESTION | **deferred** (4) |
| Extensibility & Configurability (`REQ@…aDohcf`) | Configurable documents, Configurable entities, Configurable diagrams, Pluggable Diagram-Type Verification & Rendering (4) | aggregation — motivation, OPEN QUESTION | **deferred** (4) |
| Configurable Model Attribute Schemata (`REQ@…6ZR3nk`) | 2 sub-requirements | aggregation — motivation, OPEN QUESTION | **deferred** (2) |
| Verified Referential Integrity... (`REQ@…Ee3Ff3`) | 2 sub-requirements | aggregation — motivation, OPEN QUESTION | **deferred** (2) |
| Configurable entities (`REQ@…UoHGZy`) | 2 sub-requirements (excl. the shared `pSvaRl`) | aggregation — motivation, OPEN QUESTION | **deferred** (2) |
| Authoring Tools (`REQ@…5PPAX3`) | 1 sub-requirement | aggregation — motivation, OPEN QUESTION | **deferred** (1) |
| Configurable documents (`REQ@…3cJ1Yi`) | 1 sub-requirement (excl. the shared `pSvaRl`) | aggregation — motivation, OPEN QUESTION | **deferred** (1) |
| Configurable diagrams (`REQ@…qpOBOQ`) | 1 sub-requirement (excl. the shared `pSvaRl`) | aggregation — motivation, OPEN QUESTION | **deferred** (1) |

**Totals**: 86 edges recommended for conversion to composition (all verified, including the one
initially flagged for a closer look), 7 stay aggregation on verified genuine-independent-existence
grounds, 17 deferred pending the motivation-layer open question. 86 + 7 + 17 = 110. ✓

**Not yet converting anything** — this is the "full review list FIRST" WU-G1b calls for; the
actual `artifact_edit_connection` batch (with `artifact_verify` between batches) happens after
you confirm this list, per WU-G1b's own "convert approved ones" wording.

## Sample Verdicts

| # | Group | Source → Target | Recurrence signal | Verdict | Reasoning |
|---|---|---|---|---|---|
| 1 | assurance | Assurance Module (`GRP`) → Confidential Assurance Store, Assurance Archive, Assurance Verifier, Supply-Chain & Vulnerability Connector, Assurance Knowledge Base, Bill of Materials, Security Signals Store | verified: none of the 7 targets, nor the `GRP` itself, appears as a target anywhere else in the 155-list | **COMPOSITION** *(corrected)* | These are named, assurance-specific implementation modules that exist only as part of this subsystem of this codebase — each confirmed exclusive. The `GRP` entity mechanism is a directory-facet implementation detail; conceptually it stands for a real subsystem boundary, and its members are genuine constituents of it, not a catalog of independently-meaningful things it merely references. |
| 2 | assurance | Conduct Hazard Analysis (`PRC`) → Guide Assurance Method & Standards, Verify Assurance Invariants, Author Assurance Artifacts, … (`FNC`) | same functions also aggregated by 3 other processes (`7YyhMi`, `bWETd2`, `lXql_n`) | **aggregation** | Shared function library — a function reused by 4 processes cannot be exclusively composed into any one. Genuine sharing, unaffected by the correction. |
| 3 | motivation-narrative | Extensibility & Configurability (`REQ`) → Configurable documents, Configurable entities, Configurable diagrams, Pluggable Diagram-Type Verification & Rendering (`REQ`) | targets independently meaningful; see #4 | **aggregation** *(open question — see below)* | Requirement decomposition — each child requirement stands as a real requirement on its own. Whether the corrected software-module reasoning transfers to motivation-layer decomposition is a separate question I have not resolved unilaterally; see "Open question" below. |
| 4 | motivation-narrative | Configurable documents / Configurable entities / Configurable diagrams (3 distinct `REQ`s) → **Configurable Frontmatter Schemata** (`REQ@…pSvaRl`) | same target under **3 different parents** | **aggregation** | Directly confirms the shared-membership signal — this sub-requirement cannot be "part of" all three exclusively. Genuine sharing, unaffected by the correction. |
| 5 | motivation-narrative | Achieve Unity of Effort (`GOL`) → Speed Up Architectural Planning, Provide Independent Read-Access, Plan Collaboratively, Enable Fast Feedback (`GOL`) | each sub-goal independently meaningful | **aggregation** *(open question — see below)* | Same caveat as #3 — goals are not software modules; flagged rather than mechanically corrected. |
| 6 | platform-core | Architecture Management Platform (`APP`) → Architecture Backend, GUI, CLI Tool, MCP bridges, Assurance Module (`GRP`) | verified: each of the 5 direct targets, individually, appears as a target of no other aggregation edge in the 155-list | **COMPOSITION** *(corrected)* | These are exclusively-owned source-code constituents of this one software product — deleting the project deletes them, full stop. Optionality (the Assurance Module's opt-in toggle) and in-principle extractability answer a different question than current existence-dependence; the entity's own "aggregating" wording was the modeler's word choice, not proof against composition. This was the case that surfaced the error — see correction above. |
| 7 | platform-core | Architecture Backend (`APP`) → Model Verifier (`APP`) | **retracted, twice-corrected**: `arch_mcp_stdio*.py` is a pure stdio↔HTTP proxy (no business logic, no verification import — confirmed by reading it, not just grepping around it) that forwards to `ensure_backend_running`, the SAME backend process; per `ADR@1783406851` ("One Unified Backend Authority"), the MCP servers are "mounted... from inside the backend process." There is exactly one process. My "independent composition root" reading conflated "permitted broad imports for wiring a client" with "hosts its own copy of the service graph" — unrelated facts. Model Verifier is referenced exactly once in the model and runs in exactly one process, ever. | **COMPOSITION** *(corrected again — see note below)* | No second runtime host exists; nothing defeats existence-dependence or exclusivity here after all. Same structural role as #6's targets, not a distinct one — I was wrong to draw that distinction. |
| 8 | platform-core | data objects `LeI0v-`/`QQQFYs`/`4Z28xK` (3 distinct sources, incl. diagram-authoring group) → **V-MgY1** | same target under **3 different parents** across 2 groups | **aggregation** | Same shared-membership signal as #4, cross-group. Genuine sharing, unaffected by the correction. |
| 9 | promotion-and-tiering | 2 distinct `BOB` sources → same 4 `BOB` targets (`K8XxDs`, `eGCeZq`, `55sMuE`, `wDdrUY`) | identical target set under 2 different sources | **aggregation** | Textbook shared membership — two business objects both reference the same four sub-objects. Genuine sharing, unaffected by the correction. |
| 10 | platform-core | Datatype Diagram (`BOB@…dMbHkg`) → **Classifier** (`BOB@…SQXLsh`) | single occurrence; Classifier's own description reads *"owned by a datatype diagram"* | **COMPOSITION** | Unaffected by the correction — this one was already right: the target's own definition asserts ownership/existence-dependence, and it is not referenced elsewhere in the 155-list. |

### Open question for #3/#5 (motivation-layer decomposition) — RESOLVED

**Resolution (2026-07-12, user decision): motivation-layer `REQ`/`GOL` decomposition stays
`archimate-aggregation` — not converted, and not further re-litigated for now.** All 17
motivation-layer edges in the WU-G1b review list below (the `REQ@…aDohcf`, `REQ@…6ZR3nk`,
`REQ@…Ee3Ff3`, `REQ@…UoHGZy`, `REQ@…5PPAX3`, `REQ@…3cJ1Yi`, `REQ@…qpOBOQ`, and `GOL@…FCfDuc`
rows) were left unconverted accordingly. This question is closed; do not reopen it as part of
routine WU work without a new, explicit reason to revisit.

Original open question, kept for context: the software-module correction above was argued
specifically for source code that only exists because a specific system's build/runtime
exists. Whether that reasoning mechanically transfers to requirement/goal decomposition (a
conceptual/organizational statement, not a deployable artifact) was genuinely arguable either
way — resolved by user decision above rather than by further unilateral analysis.

11–20 (recorded, verdicts only, same method — all further shared-membership or
catalog/grouping cases, all **aggregation**): the remaining `PRC→FNC` pairs in
promotion-and-tiering (`FNC@1777390445.NGjUCa`, `FNC@1777390493.A-wFZl`, etc., each also
reachable from other processes elsewhere in the 155-list); the remaining `REQ→REQ` chain
entries under motivation-narrative (`6ZR3nk`, `Ee3Ff3`, `3cJ1Yi`, `UoHGZy` and their
children — each child requirement independently meaningful, several also shared); the
remaining `APP→FNC` platform-core pairs (functions recurring under 2–3 different
application components, e.g. `saMRQ0`, `rkx32U`, `uzJGYp`, `yuFXVJ`, `NGjUCa`).

## Finding (revised after two rounds of correction)

Of the 20 sampled connections, counting individual edges: **14 are now composition** (the 7
assurance-module constituents in #1, the 5 platform constituents in #6, #7's Model Verifier,
plus #10) and **the rest stay aggregation** (#2, #4, #8, #9, and the un-tabulated #11–20
cases), all resting on genuine, model-internal sharing — the same target artifact id reachable
from ≥2 distinct sources *within the model itself*. That is the one signal that survived both
rounds of correction intact, because it doesn't depend on any claim about runtime process
topology: two different modeled sources pointing at the same target is true regardless of how
the system is deployed. Everything I got wrong (#1, #6, and #7 twice) came from treating
something *other* than that signal — optionality, hypothetical extractability, or an
unverified assumption about process topology — as if it were evidence for aggregation. It
never is. Runtime/process-topology claims about *this specific codebase* turned out to be
something I should read the deciding ADR and the actual code for, not infer from a grep and a
composition-roots list — a grep across `artifact_mcp/**` found real verification calls but
told me nothing about which process executes them; only reading `arch_mcp_stdio.py` and
`ADR@1783406851` did.

## What WU-G1b Should Do Differently Given This

- Treat the "target referenced by ≥2 sources anywhere in the 155-list" signal as the primary,
  purely mechanical filter: it is the only signal in this spike that held up under scrutiny
  both times. Those can be marked aggregation without reading content at all.
- For the remaining single-occurrence pairs, do NOT stop at "is this optional/pluggable" or
  "could this be factored out" — neither answers the existence-dependence question. Read the
  target's own description for ownership language ("owned by", "belongs to") as in #10, and
  otherwise default toward composition for an exclusively-referenced, named internal
  module of this system (#1, #6, #7's actual pattern) unless there is a *specific, read, not
  inferred* reason the target has independent existence outside this one system (a real
  second process, a separately-versioned/distributed package, genuine reuse by another
  product) — and cite the source read, not a keyword search, before relying on that reason.
- Resolve the open #3/#5 motivation-layer question (above) before batch-converting any
  single-occurrence `REQ→REQ`/`GOL→GOL` pair — this spike deliberately left it open rather
  than extending the software-module correction there without confirmation.
