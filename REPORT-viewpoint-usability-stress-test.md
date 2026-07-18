# Viewpoint Usability Stress Test — Report

RUN_ID `2607171252` · 2026-07-17 · commit `3eea9b0` · evaluator: Claude Fable 5 (Claude Code harness)
Artifacts: `test-results/usability/2607171252/` (environment.json, baseline.json, oracles.json, oracle-data*.json, logs/, gui-engine-pairs.csv, invariant-matrix.md, s1-scoring.md, fmea-calibration.json, screenshots, probes).

---

## 1. Executive summary

**What this session can claim:** every claim below marked *(observed)* is an observed system fact with API/DOM/file evidence attached; claims marked *(inspection)* are expert judgements citing a named principle; everything about persona behavior (scent rates, abandonment, time-to-first-wow, misreadings) is a **synthetic-persona hypothesis requiring human confirmation** — no human-confirmed findings exist in this run.

**Top findings by Action Priority (all High, all observed unless noted):**

1. **F1 — Misleading traversal-depth text.** The flagship impact views traverse derived relationships up to 4 hops (derived edges with hops 2 and 4 present in results), but every result's summary says "(up to 1 steps)". Four independent persona contexts wrote a false "1-hop cap" limitation into tickets/design notes. S8·O9·D9.
2. **F2 — Scope tab silently diverges from the executed query.** Restricting entity types on the Scope tab writes only declared-scope metadata (which the catalog displays); execution runs the untouched query criteria. A saved fork claims 5 types and renders 7. Reproduced on both fork (PA-A1) and create (PI-A1) paths; file-level evidence. S9·O5·D6.
3. **F3 — Result projection omits `status`.** Status filters work, but result records carry no status, so authored Status columns render "—" for every row. A compliance persona confidently drafted "no status recorded in the model" (false) into audit evidence. S8·O5·D9.
4. **F5/F28 — Predicates evaluate derived edges without disclosure; Test run shows counts only.** An authored cross-layer "layering leak" query returned 1 entity where the raw model has 0 direct leaks — the match is a derived edge; Test run names neither the entity nor the edge's provenance. The persona drafted a ticket against a modeled dependency that does not exist (self-corrected only in the source-verification phase). S8·O3·D9.
5. **F6 — Derived-vs-modeled provenance is engine-complete but GUI-absent.** The execution API carries `derived::` ids, certainty, hops, and `via_connection_ids` witness chains; no GUI surface exposes any of it — edges are not selectable, there is no edge legend, dashing is ambiguous. S7·O5·D7.
6. **F8 — Result URLs are wrong or lossy.** Anchored executions never encode the anchor (link reopens an empty dialog); after switching viewpoints via the graph dropdown the URL still names the *previous* viewpoint — a copied link actively misleads. S7·O5·D7.
7. **F9 — Empty-domain honesty.** Views over unpopulated domains (capability/migration) render junction/grouping noise with non-zero counts and never state that the substantive types are absent; three personas had to infer emptiness. S7·O5·D7 *(honesty of communication is observed; the wrong-conclusion consequence is hypothesis)*.

**Strengths confirmed:** all 26 GUI↔engine count pairs matched exactly; query-builder expressiveness is far better than personas assumed (absence predicates, cross-group boundaries, negated traceability conformance all expressible; two authored views matched independent raw-file oracles set-for-set: 31 unrealized requirements, 27 untraced components); Save As is loss-free and never mutated a source definition (byte-verified); progressive disclosure in the builder held to its deepest point; the parameter dialog and live plain-language preview are exemplary.

## 2. Method as executed; deviations; isolation fidelity

Stages S0→S6 ran in order per `PROMPT-viewpoint-usability-stress-test.md` (v2). All 12 personas completed S1; 9 non-expert personas completed S2 and S3; PH/PI/PJ completed S4 (PH with post-task source verification via follow-up message to the same context); S5 comprised the invariant matrix, matched-comparison suite, two blind heuristic passes (A: Fable-class, B: Opus-class), and FMEA calibration. Roles/models per `tools/usability_test/EXECUTION.md`; identities in environment.json. **Coverage: complete** — all stages for all 12 personas (acceptance bar exceeded; S2 for PH/PI/PJ ran merged into their S4 contexts as the prompt's stage list allows).

Isolation fidelity: every persona ran in a fresh zero-history subagent whose prompt contained only the composed brief (allowlist composer), the §7 failure table, §8 recording rules, the run-prefix rule, and (S2+) that persona's own S1 selections. No oracle, candidate route, fit-kind, or other persona's result ever entered a persona context. Browser isolation is **approximated**: all subagents share one Playwright browser; the app origin's local/session storage was cleared between personas (full-profile isolation not guaranteed).

Deviations log (also in environment.json): (1) orchestrator effort stayed at `high` for S0A/S6 (cannot switch mid-session; same model as specified). (2) ~31-minute pause after PJ's S1 (user request, token-budget window); no state changed. (3) A stale Playwright browser from a previous session was killed at S0 (automation browser only). (4) Persona screenshots resolve to the repo root; the evaluator moved them into the run directory after each run. (5) `index_generation` drifted 2→121 across the run with content counts stable; every probe was internally same-snapshot; restoration check is the integrity authority. (6) PD-A1 overran its action budget by 0 (abandoned post-save execution instead); PB-A1 overran by 5 to complete the mandated save+execute — both recorded in the logs. (7) PH-S4/PI-S4/PJ-S4 combined questions and authoring challenge in one context each (fresh per persona).

## 3. Oracles and fixture validity

36 question oracles + 12 authoring preflights in `oracles.json`, derived **independently of the viewpoint evaluator** by parsing raw entity/connection files from both repo roots (`derive_oracles.py`; counts reconcile exactly with the index: 352 model + 57 diagram-only entities; 731 + 47 connections). Fixture-invalid (as designed, verified): PC1, PI1, PI2 (no strategy/implementation population) and PI3 (0 diagrams pin a viewpoint) — run as catalog-honesty observations only. Notable oracle facts: zero raw non-technology→technology edges; 31 requirements without direct realizers / 44 without an application-reaching realization chain; 27 of 42 application components without goal/requirement trace; 28 assurance-boundary connections; exactly one dead technology element; the Confidential Assurance Store realizes no requirement and has no motivation entity within 2 hops.

Where probe corroboration was used it is recorded as **shared-evaluator corroboration**, never independent (gui-engine-pairs.csv notes generations).

## 4. Scent study (S1) — synthetic hypothesis

Full scoring in `s1-scoring.md`. Headlines (n=12 personas, 36 questions): execute-fit questions **14/14 hit@1** — name-scent for shipped fits is excellent. Non-execute questions: 8 route hits, 8 partials, 6 false scents. Two systematic false-scent clusters: **(A) realization-gap trap** — realization-named views read as gap-analysis tools (PA1, PE1, PE3, PK1, PC3); nothing in the catalog says "shows existing links only"; **(B) fixture blindness** — empty-domain views collected confident act-on-it picks (PI1, PI2) because the catalog carries no population signal. Route-class misses skew toward docs-instead-of-create: non-experts do not perceive "build it yourself" as an available route from the catalog page. All 12 personas independently flagged: no description column, no in-app docs link, and the leftover e2e test row.

## 5. Per-persona task records (S2/S4) with oracle adjudication

Logs: `logs/<P>-s2.json`, `logs/PH-s4.json` (+`PH-s4-verification.json`), `logs/PI-s4.json`, `logs/PJ-s4.json`. Every executed adequacy claim was probe-checked (26 pairs, all counts matched — gui-engine-pairs.csv). Adjudication highlights (details in `oracle-flags.md`):

- **PB**: correct sets; his "hop-capped at 1" limitation in the ticket is **wrong** (induced by F1). PB3's group-facet discovery (49/68 assurance context) matches the oracle exactly.
- **PF**: first success in 2 ordinal actions; anchored neighborhoods match raw adjacency under derivation semantics; no walkaway.
- **PC**: correctly refused to present capability coverage (fixture gap surfaced via 22-node/0-connection render + verbatim schema-drift warning); correctly declared PC4 a no-go (no cost/lifecycle data). Noise prediction confirmed: "technology" view = 118 entities vs 14 real technology-domain entities.
- **PE**: correctly refused to cite requirements-realization (returns the entire model, 352/352 — a mis-scoped shipped definition); **over-generalized** "driver→goal edges do not exist" from one sample (oracle: 7 exist; 3 of 6 drivers lack them) — contributing factor: no gap marking anywhere. Status distribution had to be hand-tallied (no aggregation/export).
- **PA**: could not derive the built/aspirational split (adequate refusal; oracle: 5 of 9 goals have app-chains); PA2's tiny blast radius (2/2) is derivation-correct but PA missed the orphaned requirement (dependents views cannot show what loses its only realizer — F-note under F6).
- **PD**: exact counts everywhere; discovered the absence-query expressibility; technology-scoped zero-connection count (1) matches the oracle exactly (File System Service); model-wide 17 vs oracle 5 explained by diagram-only/global entities in the index. Edge types visible only on entity pages, not in views (part of F6).
- **PG**: durable links exist for parameterless views only (F8); "project" name trap confirmed; label truncation caused a real misreading — an assessment node entered his design-review bullet as "an Assurance application-component".
- **PK**: policy entity findable and traceable (10/21 at 1 hop, probe-matched); no export anywhere (F22); blank Status column misattributed (F3).
- **PL**: assurance-store neighborhood sparse-but-correct; his "SQLCipher/OS-Keychain links missing" claim is a **direction artifact** (they exist as incoming serving edges; the outgoing-dependencies view hides them); genuine oracle-confirmed gaps: store realizes no requirement, no motivation within 2 hops. The 1318-connection motivation-technology-support result exposed that derived connections dominate counts without disclosure (F1-adjacent).
- **PH**: PH1 refuted own ticket in source verification (derived-edge mechanism, F5); PH2 confirmed serving/realization contract surface is genuinely modeled — GUI blocked per-node inspection (F12); PH3 confirmed provenance is a GUI-surface gap (F6); PH-A1 reached the deepest authoring path but the scale rule silently no-opped (F4).
- **PI**: two audience forks saved but neither renders (F7) and the exec fork's scope restriction didn't execute (F2); could not find Save As (evaluator verified it exists — discoverability hypothesis H4); PI1/PI2 fixture-gap honesty (F9); PI3/PI4 no staleness/changelog surfaces (F27).
- **PJ**: conformance query fully expressible; PJ-A1's 27-component set is **set-identical** to the independent oracle; tier-hygiene review (1 delete, 4 duplicate forks, 3-way impact cluster, 3 promotion candidates); proposed 8-pin starter set with honest no-fit residue; Save-As governance verdict: no provenance/lineage → unauditable at scale. One PJ claim is **unsupported by session evidence** and excluded: that diagrams show "stale-pin (W180) warnings" (no diagram pins any viewpoint in this workspace).

## 6. Authoring & Save As study; matched comparisons; invariants

**Authoring (S3/S4):** 12 challenges attempted; 11 definitions saved (+2 evaluator fixtures), all run-prefixed, manifested, and probe-verified; PC-A1 ended as a documented validation dead end (inherited schema-drift blocks a fork's save — F17). Oracle-exact results: PK-A1 (31 unrealized requirements, set-identical), PJ-A1 (27 untraced components, set-identical), PE-A1 (104 draft motivation elements, count-exact), PD-A1/PL-A1/PB-A1 consistent with raw expectations. Time-to-first-useful (synthetic descriptor): PF-A1 = 16 ordinal actions for fork+recolor+re-execute.

**Matched comparison suite** (only these cells support variance claims; invariant-matrix.md):
representation cell PASS (104/195 identical across table/graph-route/diagram/probe); anchored-vs-filter cell adjudicated (divergence = derived-edge evaluation, F5); limits cell PASS (truncation flagged + X/Y disclosure); fork-unchanged cell PASS (identical sets; source untouched); Save-As-vs-blank cell PASS (identical entity sets across module original, GUI fork, MCP from-blank rebuild).

**Invariant matrix** (invariant-matrix.md): Inv 1 PASS (26/26 pairs + multi-surface cell), Inv 2 PASS for match-mode rules, **Inv 4 FAIL — silent no-op scale rule** (F4), Inv 3 PASS, Inv 5 qualified PASS, Inv 6 PASS (byte-verified thrice), **Inv 7 partial FAIL** (GUI "Save as…"/"Test run"/"style rule" vs docs "forking"/"live preview"/"styling rules"), Inv 8 PASS.

## 7. Heuristic consolidation (independent expert passes, n=2, two model classes)

Pass A: 28 violations (logs/heuristic-pass-A.json); Pass B: 23 (logs/heuristic-pass-B.json). High agreement on: catalog lacks search/sort/filter/description (HA-2/3/4≈HB-1/2), editor not URL-addressable + silent discard (HA-5/10≈HB-5/7), spurious read-only error banner (HA-6≈HB-8), unlabeled token swatches & color-for-shape channels (HA-8/9≈HB-9), no graph legend for type codes (HA-14≈HB-12), lossy/wrong URLs (HA-15≈HB-14), raw-ID confirmation & unexplained fuzzy matches in the picker (HA-16≈HB-15/16), unreadable initial diagram fit (HA-19≈HB-17), slug-vs-name titling (HA-20≈HB-18), inert tables with empty Style column (HA-21/22≈HB-19/20), −∞/∞ scale bounds (HA-25≈HB-21), empty-domain noise (HA-24≈HB-22), duplicate names in pickers (HA-26≈HB-4). Unique-to-A: radial-layout blank-out (HA-12, sev 3), false "No entities match" after Cancel (HA-17, sev 3), disappearing Spacing controls (HA-18), active-layout label invisible (HA-13), comparator jargon (HA-7), summary grammar (HA-28). Unique-to-B: `global-artifact-reference` selectable in Scope picker (HB-10 — contradicts the standing authoring-surface exclusion rule), ArchiMate jargon without help on General tab (HB-6), inconsistent execute-UIs across representations (HB-23). Both passes independently reproduced the persona-visible catalog/legibility complaints, strengthening those from hypothesis toward inspection-grade.

## 8. Findings register + FMEA

Evidence classes: OSF = observed system fact; INS = inspection finding; HYP = synthetic hypothesis. S/O/D per calibrated anchors (fmea-calibration.json; observed vs predicted separated by the Reproduced column). AP = Action Priority (High = S≥9, or S≥7 ∧ (O≥5 ∨ D≥7)).

| ID | Title | Class | Evidence | Reproduced | Heuristic | S | O | D | AP |
|---|---|---|---|---|---|---|---|---|---|
| F1 | Query summary says "(up to 1 steps)"; traversal is derived ≤4 hops | OSF | probe hop data; src yaml; 4 persona artifacts | yes (4×) | visibility of status | 8 | 9 | 9 | **High** |
| F2 | Scope-tab edits diverge from executed query (fork+create) | OSF | viewpoints.yaml fork block; probes PA-A1/PI-A1 | yes (2×) | consistency | 9 | 5 | 6 | **High** |
| F3 | Projection omits status → blank authored Status columns; misattribution | OSF | probe entity keys; PE-A1/PK-A1 | yes (2×) | visibility of status | 8 | 5 | 9 | **High** |
| F4 | Scale rule w/ unresolvable attribute silently no-ops (Inv-4 FAIL) | OSF | probe-PH-A1 (styled={}, legends=[]) vs GUI legend | once | error prevention | 7 | 3 | 9 | **High** |
| F5 | 'has a connection' evaluates derived edges undisclosed | OSF | PH1 1-vs-0 adjudication; witness chain | once | match w/ real world | 8 | 3 | 9 | **High** |
| F6 | Derived/modeled provenance engine-complete, GUI-absent (edges unselectable, no edge legend) | OSF | probe via_connection_ids; PH3 sweep | yes | recognition | 7 | 5 | 7 | **High** |
| F7 | Diagram render fails at full scale (PlantUML line 767), no degradation | OSF | PI-A1 ×2 | yes (2×) | error recovery | 5 | 5 | 1 | Med |
| F8 | URLs lossy (anchor never encoded) or wrong (stale viewpoint param after dropdown switch) | OSF | PG3, HA-15, HB-14 | yes (3×) | user control | 7 | 5 | 7 | **High** |
| F9 | Empty-domain results render junction noise; absence never stated | OSF | PC1/PI1/PI2, HA-24, HB-22 | yes (5×) | match w/ real world | 7 | 5 | 7 | **High** |
| F10 | Cancel in param dialog → false "No entities match" | OSF | HA-17 | once | error recovery | 7 | 3 | 5 | **High** |
| F11 | Spurious 'read-only-definition' error banner on module View | OSF | HA-6, HB-8 | yes (2×) | error recovery | 3 | 5 | 3 | Med |
| F12 | Dense graphs: no zoom/fit; radial blanks w/o anchor; node clicks blocked/unstable; labels truncated → misreading | OSF (+HYP consequence) | PH2, PG3 misread, HA-12/13, HB-13 | yes (4×) | flexibility | 7 | 5 | 5 | **High** |
| F13 | No legend for node type codes/colors in exploration | OSF | HA-14, HB-12 | yes (2×) | recognition | 3 | 9 | 5 | Med |
| F14 | Catalog: no search/sort/filter/description/representation/param indicators; scope dumps | OSF | 12 personas + HA-2/3/4 + HB-1/2 | yes (14×) | recognition | 3 | 9 | 5 | Med |
| F15 | Duplicate display names, no tier marker in pickers | OSF | HA-26, HB-4 | yes (2×) | error prevention | 5 | 3 | 7 | Med |
| F16 | Editor unaddressable; Back silently discards; no Save-as cancel | OSF | HA-5/10, HB-5/7 | yes (2×) | user control | 5 | 5 | 3 | Med |
| F17 | Fork inherits schema-drifted rule → save blocked by un-authored error | OSF | PC-A1 verbatim errors | once | error recovery | 5 | 3 | 5 | Med |
| F18 | Validation surfaces only at save-time ('exists takes no value') | OSF | PC-A1 | once | error prevention | 3 | 3 | 5 | Low |
| F19 | Scale legend bounds −∞/∞ under Auto | OSF | PH-A1, HA-25, HB-21 | yes (2×) | visibility | 3 | 3 | 5 | Low |
| F20 | group_by=project + Clusters renders no visible grouping (4 groups in data) | OSF | probe-PG-A1 group distribution; screenshots | once | visibility | 5 | 3 | 7 | Med |
| F21 | Tables: inert rows, empty Style column, no sort | OSF | PK/PE, HA-21/22, HB-19/20 | yes (3×) | flexibility | 5 | 5 | 3 | Med |
| F22 | No export on any execution surface | OSF | PA3, PK1, PE2 | yes (3×) | flexibility | 5 | 5 | 1 | Med |
| F23 | GUI↔docs terminology drift (Save as/Test run/style rule); no in-app help link | OSF | Inv-7 sample; HA-27; PI3 | yes | help & docs | 3 | 5 | 5 | Med |
| F24 | e2e leftover row in production catalog | OSF | baseline + 12/12 persona notes | yes (12×) | aesthetic | 3 | 9 | 1 | Low |
| F25 | global-artifact-reference selectable in Scope picker | OSF | HB-10 | once | error prevention | 5 | 3 | 7 | Med |
| F26 | Picker: diagram-internals outrank model entities; raw-ID confirmation; unexplained fuzzy matches | OSF | HA-16, HB-15/16, PI2, PL1 | yes (4×) | match w/ real world | 5 | 5 | 5 | Med |
| F27 | No staleness/pin-version/changelog surface (product gap, honest) | OSF | PI3/PI4, PJ | yes | visibility | 5 | 3 | 7 | Med (predicted) |
| F28 | Test run reports counts only — no matched-entity names | OSF | PD3, PH1 | yes (2×) | visibility | 5 | 5 | 5 | Med |
| F29 | Edge styling cannot condition on endpoint groups (no boundary emphasis) | OSF | PL-A1 | once | flexibility | 3 | 3 | 5 | Low |
| F30–F34 | Minor: invisible active-layout label; summary grammar; disappearing Spacing controls; slug-vs-name titling; unlabeled token swatches / color-for-shape | OSF | HA-13/28/18/20, HB-9/18 | yes | various | ≤3 | 3–5 | 3–5 | Low |
| H1 | Realization-gap trap (false scent cluster) | HYP | s1-scoring | 5 personas | match w/ real world | 7 | 5 | 7 | High (needs human confirmation) |
| H2 | Fixture-blindness scent (no population signal) | HYP | s1-scoring | 2 personas | visibility | 7 | 3 | 7 | High (needs human confirmation) |
| H3 | Non-experts don't perceive "create" as a route | HYP | s1-scoring | 5 personas | flexibility | 5 | 5 | 5 | Med (needs human confirmation) |
| H4 | Save As undiscovered by an expert persona | HYP | PI-A1 vs evaluator verification | once | recognition | 5 | 3 | 5 | Med (needs human confirmation) |

RPN available as secondary sort from the table (S·O·D); AP is the ranking authority.

## 9. Recommendations

**High Action Priority — quick wins** (small, isolated):
- **R1 (F1)**: Fix the summary generator to describe `include_connected` traversal (mode + max_hops) and stop leaking the derived-attribute bound. Best practice: *summaries must describe executed semantics* (match between system and world). Doesn't apply: none. Component: query-summary renderer (src viewpoint query summary builder). Deps: none. Estimate S (high conf). Validation: summary for element-dependents states "derived, up to 4 steps"; regression test on summary text vs definition.
- **R10 (F10)**: On param-dialog cancel show "not executed" state, never the empty-result message. Component: graph explorer param flow. S (high conf). Validation: cancel → neutral state.
- **R24 (F24)**: Sweep test artifacts from the engagement catalog; add slug-pattern lint for e2e fixtures. Component: engagement viewpoints.yaml + CI. S (high conf).
- **R19 (F19/F4 symptom)**: Resolve Auto scale bounds to observed min/max and label endpoints numerically. Component: scale legend renderer. S (medium conf).

**High Action Priority — substantial**:
- **R2 (F2)**: Single source of truth for type restriction: Scope-tab edits must rewrite (or visibly bind to) query criteria, or the editor must refuse to let scope and query diverge (warn + one-click sync). Best practice: *one representation of intent* (consistency; DRY for definitions). Doesn't apply: intentional admissible-vs-selected distinction for parameterized viewpoints — then the UI must label the difference explicitly. Component: viewpoint editor Scope/Query tabs + definition validator (E-code for divergence). Deps: definition schema docs. M (high conf). Validation: fork PA-A1 scenario; catalog row, definition, and execution agree.
- **R3 (F3)**: Add status (and last-updated) to the projection entity record; render status tokens in tables. Doesn't apply: if status is deliberately excluded for confidentiality tiers, say so in the cell. Component: execution projection builder + table renderer. M (high conf). Validation: PE-A1 re-run shows draft badges; probe carries status.
- **R4 (F4)**: Enforce Invariant 4 in the engine: a style rule whose scale attribute resolves on zero items must emit a warning in the execution payload and the GUI. Component: presentation resolver. M (high conf). Validation: PH-A1 re-run yields visible "rule matched nothing" notice; probe carries warning.
- **R5 (F5+F28)**: Test run must list matched entities (first N + names) and disclose when a predicate matched via derived edges; add a modeled-only toggle on connection predicates. Component: query builder Test run + predicate evaluator options. M (medium conf). Validation: PH1 recipe shows the store + "matched via derived access (2 hops)".
- **R6 (F6)**: Surface the existing provenance: selectable edges; edge detail panel showing type, certainty, hops, witness chain (linked); an edge legend mapping style→{modeled, derived}. Best practice: *don't hide provenance the engine already has*. Component: graph explorer + diagram renderer sidebars. M–L (high conf that data is available — verified). Validation: PH3 walkthrough succeeds without source access.
- **R8 (F8)**: Encode viewpoint + parameters (+ layout) in execution URLs; fix the stale-viewpoint param on dropdown switch. Component: SPA router for /graph and /viewpoints/diagram. M (high conf). Validation: reload and share reproduce the exact result.
- **R9 (F9)**: When a result contains only structural types (junction/grouping) or when scoped substantive types have zero instances, say so: "This model contains no capability elements (0 of the 6 scoped types present)". Component: execution result header. S–M (high conf). Validation: capability-map/migration honesty check.
- **R12 (F12+F13)**: Graph explorer ergonomics: fit-to-view/zoom controls + minimap, stop force-layout before enabling clicks, guard radial without anchor, label wrapping/tooltips, and a node type/color legend. Component: exploration surface. L (medium conf). Validation: HA-12/13 scenarios + PH2 node inspection on 183-node view.

**Medium priority** (selection): R7 (F7) cap/tile PlantUML renders with a friendly fallback and "render smaller scope" hint; R14 (F14) catalog columns (description, representation icon, parameter marker, population hint) + search/sort/filter; R15 (F15) tier badges in all pickers; R16 (F16) route the editor (`/viewpoints/:slug/edit`), dirty-state confirm, Save-as cancel; R17/R18 (F17/F18) validate style rules at edit time and quarantine inherited drifted rules on fork (auto-disable with notice instead of blocking save); R21/R22 (F21/F22) linked table rows, sortable columns, CSV/PNG export with provenance footer (query + version + executed_at + generation); R23 (F23) align docs vocabulary with GUI ("Save as…", "Test run", "style rule") and add an in-app help link; R25 (F25) re-apply the internal-type exclusion to the Scope picker; R26 (F26) rank model entities above diagram internals, echo names not raw ids; R27 (F27) record fork/pin provenance (origin slug+version) and surface staleness (PJ's governance ask); R20 (F20) make cluster layout honor group_by or remove the option.

Triage fields per recommendation: owner-component named above; dependencies: R6 depends on edge-selection work also needed by R12; estimates are bands (S/M/L) with stated confidence, not commitments.

## 10. Limitations and human-validation shortlist

Synthetic personas (all behavioral metrics are hypotheses); single-model evaluator (one orchestrator judged adequacy, mitigated by independent raw-file oracles and two heuristic passes on different model classes); fixture gaps (strategy/implementation domains empty — capability/migration UX judged only for honesty, not utility); catalog scale (34 definitions; 20-team-scale claims out of scope); browser isolation approximated (shared Playwright profile, storage cleared per persona); persona action budgets consumed by tool mechanics in places (stale refs, tab switches) — ordinal counts are conservative.

**Most deserving of a small human-validation round:** (1) the F1 misleading-depth text — do real users also derive the 1-hop-cap belief?; (2) scent clusters H1/H2 (realization-gap trap; fixture blindness); (3) anchor finding + first-useful-result flow for a real solo developer (PF's 2-click wow vs 16-action fork); (4) Save As discoverability (H4); (5) result trust: do real analysts notice the blank Status column and what cause do they attribute?

## 11. Cleanup & restoration statement

(Completed after report assembly — see below.)

- Catalog/pins restoration: **VERIFIED** — cleanup helper deleted exactly the 14 manifest-listed `usability-2607171252-*` slugs and byte-verified the post-run catalog and pin list against `baseline.json`.
- Whole-worktree restoration: **VERIFIED** — re-ran the S0 captures: same commit SHA `3eea9b0`, `git status --porcelain` differences limited to `test-results/usability/2607171252/**` and this report, `git diff HEAD --binary` hash unchanged (tracked files untouched), engagement `viewpoints.yaml` hash restored to `62635c5c…`, no new untracked files under `engagements/` or `spec/`.

---

## Post-run addendum — owner review round (2026-07-17)

The repository owner reviewed the flagged items; adjudications are recorded in
`PROPOSALS-viewpoint-usability-improvements.md` (§"Owner adjudications incorporated").
Two affect how this report should be read:

1. **FMEA severity anchor: unresolved by deliberate abstention.** The owner declined
   to endorse either S-anchor reading, on the valid ground that the link between
   agent tasking/prompts/capabilities and synthetic-persona "confident wrong action"
   is uncharacterized. Findings whose S rests on persona confidence (F1, F3, F5)
   therefore carry dual readings (S8–9 literal / S7 primary-result-correct); the
   ordering *within* the High band in §8 is provisional; no finding crosses the
   High/Medium boundary under either reading. See `fmea-calibration.json`
   (`owner_review_outcome`).
2. **Hypothesis dispositions:** H1 (realization-gap expectation) was endorsed by the
   owner as the intended design and is now a committed proposal (P-17), no longer
   awaiting user validation; H4's Save-As placement was endorsed as-designed (the
   remaining fix is the "View" action label). The empty strategy/implementation
   domains are confirmed intentional, making the F9 honest-empty messaging the
   load-bearing fix for those viewpoints.
