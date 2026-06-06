# TASKS — C4 self-model implementation tracker

**Single source of truth for progress.** On resume (new session / after compaction),
trust **this file + repo state**, never conversation memory. Tick a box the moment its
unit is done **and committed**; add the short commit ref.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done.

**Plans (authoritative detail):**
- **C4** = `PLAN-c4-self-model-narrative.md` (model + diagram spec; §10 = exact ops/IDs)
- **UNIFY** = `PLAN-backend-runtime-unification.md` (P3+P4)
- **CLEANUP** = `PLAN-archimate-next-rule-conformance-and-repository-cleanup.md` (P1)
- **PROJECTOR base (done)** = `plans/meta-ontology-v2/PLAN-c4-renderer-fix.md`

**Global gates:** every diagram needs P1+P2; D2/D4 also need P3+P4.
**Memory:** update `…/memory/project_c4_self_model_plan.md` at each stage boundary.

---

## Stage 0a — P1 repo cleanup  *(gates all diagrams)*  — owner: CLEANUP plan
- [ ] P1 executed per CLEANUP plan (its own checklist is authoritative)
- [ ] Invalid `service↔component` realizations replaced with `function/process → service` chains (C4 §2.4/§3.1)
- [ ] **Representative** `component→behaviour→service` chains wired (2–3 per service, C4 §3.1)
- [ ] **Acceptance:** `artifact_verify(repo_scope="engagement", return_mode="full")` → **0 errors**

## Stage 0b — C4 additive model: Groups R, K, B, X  *(parallel with 0a/0c)*
- [ ] R1 create `application-component` **AMP** (C4 §10.1) → record ID
- [ ] B1 create 4 MCP bridges + 4 stdio `application-interface`s (C4 §10.1/§10.3) → record IDs
- [ ] B2 wire `Backend S→ bridge`, `bridge As→ own interface`, `interface S→ $HOST` (C4 §10.3)
- [ ] R2 `AMP Ag→ {Backend, GUI, CLI, 4 bridges}`; `AMP Asc– AMS` (C4 §10.2)
- [ ] K  `Backend Ag→` the 7 omitted components (C4 §10.4)
- [ ] X1 create external **AI Agent Host** `$HOST`, **Git Hosting**, **Supply-Chain Sources** (C4 §10.1); assign AI Agent role to `$HOST`; retire the 4 Agentic LLM Applications (migrate edges → bulk_delete)
- [ ] X2 `Git Hosting S→ Git Sync`; `Supply Fl→ Connector`; real interface→actor serving edges (C4 §3.8/§10.7)
- [ ] **Acceptance:** engagement verify clean; AMP/bridges/host reachable

## Stage 0c — P2 projector delta  *(builds on the done renderer-fix)*
- [ ] P2.1 reverse `serving` **direction** (label already done) → `Consumer --uses--> Service`
- [ ] P2.2 additive **validated inclusion** (inclusion can add graph-justified elements)
- [ ] P2.3 bounded **context roll-up** + the acceptance contract (C4 §4 P2)
- [ ] P2.4 **passive-store** dependencies in component views
- [ ] P2.5 **grouping scope** support (for D4)
- [ ] P2.6 deterministic traversal + size limits  *(reuse the `usePagination` bounding pattern)*
- [ ] P2.7 tests: preview / derivation / refresh / render parity
- [ ] **Acceptance:** D1–D4 preview render correctly against a scratch scope

## Stage 1 — Backend runtime unification (P3+P4) + Groups M/S + reconcile  — owner: UNIFY
- [ ] W1 mount 4 MCP endpoints in `arch-backend` (assurance gated)
- [ ] W2 four thin stdio bridges (split combined assurance bridge)
- [ ] W3 CLI audit: route artifact-mutating commands through backend; bootstrap/config exempt
- [ ] W4 CLI requires running backend (clear error); assurance unavailable/locked contract
- [ ] W5 tests: cross-surface parity, single-writer concurrency, gating
- [ ] MIG reframe **MCP Model Server** & **Assurance MCP Server** → Backend-internal **endpoint adapters** (`Backend Ag→`), drop invalid realizations (C4 §3.4)
- [ ] M  create `grouping` **Assurance Module** + aggregations (C4 §10.5)
- [ ] S  `artifact R→ data-object`; `Backend Ac→ data-object`; baseline **no active-store container** (C4 §10.6)
- [ ] REC apply the superseded-banner changes to `PLAN-assurance-architecture-model.md`'s model entities
- [ ] **Acceptance:** UNIFY §5 (no mutation path bypasses the write queue; 4 endpoints; 4 bridges)

## Stage 2 — Author diagrams (per-view gates, C4 §6/§10.8)
- [ ] D1 `c4-system-context` scope=AMP  *(gate P1,P2,R,B,X)*
- [ ] D3 `c4-component` scope=Backend  *(gate P1,P2,K,MIG)*
- [ ] D2 `c4-container` scope=AMP  *(gate P1,P2,P3,P4)*
- [ ] D4 `c4-component` scope=Assurance Module  *(gate P1,P2,P3,M,S)*
- [ ] D5 layered dynamic views (C4 §6.1) + **author the query/navigate use-case view** (the one open TODO)
- [ ] **Final:** repo-wide `artifact_verify` clean; memory updated
