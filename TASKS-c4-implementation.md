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
- [x] P1 executed per CLEANUP plan (its own checklist is authoritative)
      **DONE (branch c4-impl, commits dfc277f–c00ada1):**
      - §2.5 drift items all fixed (E350/E312/E011/E155/W042) — prior session
      - §3.1 normative fixture `connection_rules_snapshot1.yaml` + parity tests
      - §3.2 connections.yaml reconciled: added 4 missing ArchiMate rules (app-component→data-object access, app-component→function/process assignment, technology-node→artifact aggregation, behavior→goal influence)
      - §3.3–§3.5 semantic triple validator (`_verifier_rules_semantic.py`, E126/W126), write-path enforcement, repository-wide verifier
      - §3.6 W126 realization-quality guidance in verifier
      - §4.1 all invalid component↔service/structure→behavior realizations removed; technology-node composition→aggregation fixed; process→goal influence restored; 5 function→service realization chains added; python-runtime serving chain added
      **Result:** `artifact_verify(engagement)` → 0 errors 0 warnings (c00ada1)
- [x] Invalid `service↔component` realizations replaced with `function/process → service` chains (C4 §2.4/§3.1) — c00ada1
- [x] **Representative** `component→behaviour→service` chains wired (2–3 per service, C4 §3.1) — c00ada1
      authoring(×2), validation(×1), discovery(×1), assurance(×1)
- [x] **Acceptance:** `artifact_verify(repo_scope="engagement", return_mode="full")` → **0 errors** (7318249 — 0 errors 0 warnings, 570 files)

## Stage 0b — C4 additive model: Groups R, K, B, X  *(parallel with 0a/0c)*
**Entity IDs:**
- `$AMP` = `APP@1780783671.hkrdtm` (Architecture Management Platform)
- `$ARDB` = `APP@1780783708.Ne0utf` | `$AWRB` = `APP@1780783709.etTj9M`
- `$SRDB` = `APP@1780783710.iu_kKL` | `$SWRB` = `APP@1780783711.js9xHR`
- `$IARDB` = `AIF@1780783712.xJdQZ_` | `$IAWRB` = `AIF@1780783713.Ik61W4`
- `$ISRDB` = `AIF@1780783714.bkIdu0` | `$ISWRB` = `AIF@1780783715.qf_Jla`
- `$HOST` = `APP@1780783991.v6AXNw` | `$GITHOST` = `APP@1780783992.Je9pmw` | `$SUPPLY` = `APP@1780783993.JqIBPJ`

- [x] R1 create `application-component` **AMP** (C4 §10.1) → `APP@1780783671.hkrdtm` — a21a529
- [x] B1 create 4 MCP bridges + 4 stdio `application-interface`s (C4 §10.1/§10.3) → IDs above — a21a529
- [x] B2 wire `Backend S→ bridge`, `bridge As→ own interface`, `interface Asc→ $HOST` (C4 §10.3)
      Note: NEXT rules prohibit `archimate-serving` from interface→component; used `archimate-association` for interface↔$HOST and interface↔actor edges — a21a529
- [x] R2 `AMP Ag→ {Backend, GUI, CLI, 4 bridges}`; `AMP Asc– AMS` (C4 §10.2) — a21a529
- [x] K  `Backend Ag→` the 7 omitted components (C4 §10.4) — a21a529
- [x] X1 create external **AI Agent Host** `$HOST`, **Git Hosting**, **Supply-Chain Sources** (C4 §10.1); assign AI Agent role to `$HOST`; retire the 4 Agentic LLM Applications (bulk_delete) — 88efc6c
- [x] X2 `Git Hosting S→ Git Sync`; `Supply S→ Connector`; real interface Asc→ actor edges (C4 §3.8/§10.7) — 88efc6c
      Note: `archimate-flow` not permitted app-component→app-component; used `archimate-serving` for Supply→Connector
- [x] **Acceptance:** engagement verify clean (589 files, 0 errors, 0 warnings) — 88efc6c; AMP/bridges/host present ✓

## Stage 0c — P2 projector delta  *(builds on the done renderer-fix)*
- [x] P2.1 reverse `serving` **direction** → `Consumer --uses--> Provider` — f274e57
- [x] P2.2 additive **validated inclusion** (graph-justified entities added) — f274e57
- [x] P2.3 bounded **context roll-up**: system-context traverses all structural descendants;
      internal entities remap to scope root; self-loops + duplicates removed — f274e57
      Note: container/component roll-up discovers neighbours from deep descendants but
      does NOT yet remap to nearest visible ancestor (out of scope for 0c)
- [x] P2.4 **passive-store** `data-object` + `grouping` in `_COMPONENT_INTERNAL_TYPES` — f274e57
- [x] P2.5 **grouping scope** support — added to all type sets — f274e57
- [x] P2.6 `archimate-assignment` in `_NESTING_TYPES`; `archimate-association` in `_NEIGHBOR_TYPES`
      with root-level skip; `_MAX_ITEMS=150` hard cap + `_MAX_ROLLUP_DEPTH=8` — f274e57
- [x] P2.7 18 tests in `test_c4_p2_projector.py` covering P2.1–P2.6 — f274e57
- [x] **Acceptance:** `zuban check` + full suite green (940 pass, 1 pre-existing skip) — f274e57

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
